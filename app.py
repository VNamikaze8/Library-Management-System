
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_connection, initialize_database
from werkzeug.security import check_password_hash
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "library_devops_secret_key"

FINE_PER_DAY = 10


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_connection()
        admin = conn.execute(
            "SELECT * FROM admins WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid username or password!")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    total_books = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    issued_books = conn.execute(
        "SELECT COUNT(*) FROM issued_books WHERE status='Issued'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_books=total_books,
        total_students=total_students,
        issued_books=issued_books
    )


@app.route("/books", methods=["GET", "POST"])
def books():
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        quantity = int(request.form["quantity"])

        if quantity < 1:
            flash("Quantity must be at least 1.")
        else:
            conn.execute(
                """INSERT INTO books
                (title, author, category, quantity, available)
                VALUES (?, ?, ?, ?, ?)""",
                (title, author, category, quantity, quantity)
            )
            conn.commit()
            flash("Book added successfully!")

    search = request.args.get("search", "")

    book_list = conn.execute(
        """SELECT * FROM books
        WHERE title LIKE ? OR author LIKE ?
        ORDER BY id DESC""",
        (f"%{search}%", f"%{search}%")
    ).fetchall()

    conn.close()

    return render_template("books.html", books=book_list, search=search)


@app.route("/update_book/<int:id>", methods=["GET", "POST"])
def update_book(id):
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    book = conn.execute(
        "SELECT * FROM books WHERE id=?", (id,)
    ).fetchone()

    if not book:
        conn.close()
        flash("Book not found!")
        return redirect(url_for("books"))

    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        quantity = int(request.form["quantity"])

        issued_count = book["quantity"] - book["available"]

        if quantity < issued_count:
            flash("Quantity cannot be less than currently issued books.")
        else:
            available = quantity - issued_count

            conn.execute(
                """UPDATE books
                SET title=?, author=?, category=?, quantity=?, available=?
                WHERE id=?""",
                (title, author, category, quantity, available, id)
            )
            conn.commit()
            conn.close()
            flash("Book updated successfully!")
            return redirect(url_for("books"))

    conn.close()
    return render_template("update_book.html", book=book)


@app.route("/delete_book/<int:id>")
def delete_book(id):
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    active = conn.execute(
        "SELECT id FROM issued_books WHERE book_id=? AND status='Issued'",
        (id,)
    ).fetchone()

    if active:
        flash("Cannot delete a book that is currently issued.")
    else:
        conn.execute("DELETE FROM books WHERE id=?", (id,))
        conn.commit()
        flash("Book deleted successfully!")

    conn.close()
    return redirect(url_for("books"))


@app.route("/students", methods=["GET", "POST"])
def students():
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]

        try:
            conn.execute(
                "INSERT INTO students (name, email, phone) VALUES (?, ?, ?)",
                (name, email, phone)
            )
            conn.commit()
            flash("Student registered successfully!")
        except Exception:
            flash("Student email already exists or details are invalid.")

    student_list = conn.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template("students.html", students=student_list)


@app.route("/issue", methods=["GET", "POST"])
def issue():
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    if request.method == "POST":
        book_id = request.form["book_id"]
        student_id = request.form["student_id"]

        book = conn.execute(
            "SELECT * FROM books WHERE id=?", (book_id,)
        ).fetchone()

        student = conn.execute(
            "SELECT * FROM students WHERE id=?", (student_id,)
        ).fetchone()

        if not book or not student:
            flash("Invalid book or student.")
        elif book["available"] <= 0:
            flash("Book is unavailable.")
        else:
            issue_date = date.today()
            due_date = issue_date + timedelta(days=14)

            conn.execute(
                """INSERT INTO issued_books
                (book_id, student_id, issue_date, due_date)
                VALUES (?, ?, ?, ?)""",
                (book_id, student_id, str(issue_date), str(due_date))
            )

            conn.execute(
                "UPDATE books SET available=available-1 WHERE id=?",
                (book_id,)
            )

            conn.commit()
            flash("Book issued successfully!")

    book_list = conn.execute(
        "SELECT * FROM books WHERE available > 0"
    ).fetchall()

    student_list = conn.execute(
        "SELECT * FROM students"
    ).fetchall()

    conn.close()

    return render_template(
        "issue.html",
        books=book_list,
        students=student_list
    )


@app.route("/return")
def return_book():
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    issued_list = conn.execute(
        """SELECT issued_books.*, books.title, students.name
        FROM issued_books
        JOIN books ON issued_books.book_id = books.id
        JOIN students ON issued_books.student_id = students.id
        WHERE issued_books.status='Issued'"""
    ).fetchall()

    conn.close()

    return render_template("return.html", issued_books=issued_list)


@app.route("/return_book/<int:id>")
def process_return(id):
    if "admin" not in session:
        return redirect(url_for("login"))

    conn = get_connection()

    record = conn.execute(
        "SELECT * FROM issued_books WHERE id=? AND status='Issued'",
        (id,)
    ).fetchone()

    if record:
        return_date = date.today()
        due_date = date.fromisoformat(record["due_date"])

        overdue_days = max(0, (return_date - due_date).days)
        fine = overdue_days * FINE_PER_DAY

        conn.execute(
            """UPDATE issued_books
            SET return_date=?, fine=?, status='Returned'
            WHERE id=?""",
            (str(return_date), fine, id)
        )

        conn.execute(
            "UPDATE books SET available=available+1 WHERE id=?",
            (record["book_id"],)
        )

        conn.commit()
        flash(f"Book returned! Overdue fine: Rs. {fine}")
    else:
        flash("Invalid return request.")

    conn.close()
    return redirect(url_for("return_book"))


if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=5000, debug=True)
