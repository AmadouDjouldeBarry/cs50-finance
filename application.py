import os
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # cash 
    cash = db.execute("select cash from users where id = :id", id=session["user_id"])[0]['cash']
    rows = db.execute("select symbol,quantity from history where user_id=:user_id and quantity > 0", user_id=session["user_id"])
    result = []
    for row in rows:
        name = lookup(row['symbol'])['name']
        total = lookup(row['symbol'])['price'] * row['quantity']
        price = lookup(row['symbol'])['price']
        result.append({"name": name, "symbol": row["symbol"], "price": price, "total": total, "share": row["quantity"]})
    
    return render_template("index.html", result=result, cash=cash)
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        
        if not (request.form.get('symbol')) or not (request.form.get('shares')):
            return apology("sorry must provide symbol and shares")
        # getting the symbol from user
        symbol = lookup(request.form.get('symbol'))
        
        # check if symbol exist
        
        if not symbol:
            return apology("sorry symbol doesn't exist")
        try:
            share = int(request.form.get('shares'))
        except ValueError:
            return apology("sorry shares must be  interger")
            
        if share <= 0:
            return apology("sorry shares must be  interger")
        # get the total price of transaction
        symbol = lookup(request.form.get('symbol'))['symbol']
        price = share * lookup(request.form.get('symbol'))['price']
        
        # check if the user have enough money
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])[0]['cash']
        
        if price > cash:
            return apology("sorry u dont't have money to buy")
        
        # else update amout of cash in users databse
        db.execute("update users set cash = cash - :cost where id =:id", cost=price, id=session["user_id"])
        
        # get current date
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # get current price
        current_price = lookup(request.form.get('symbol'))['price']
        # add to transaction table
        db.execute("insert into all_transactions values(?,?,?,?,?)", session["user_id"], symbol, share, current_price, date)
        
        # history table
        current_symbol = db.execute("select symbol from history where user_id =:user_id and symbol=:symbol",
                                    user_id=session["user_id"], symbol=symbol)
        # if symbol is new we add symbol else we addtion with quantity of stock
        if not current_symbol:
            db.execute("insert into history values(?,?,?)", session["user_id"], symbol, share)
        else:
            db.execute("update history set quantity = quantity +:new_q where user_id =:user_id and symbol =:symbol ",
                       new_q=int(request.form.get('shares')), user_id=session["user_id"], symbol=symbol)
        # redirct to homepage
        flash("Bought!")
        return redirect("/")
    return render_template("buy.html")
        

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM all_transactions WHERE user_id = ?", session["user_id"])
    if not rows:
        return apology("don't have any history")
        
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")
           
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))
        if not symbol:
            return apology("Share doesn't exist")
        symbol['price'] = usd(symbol['price'])
        return render_template("quoted.html", symbol=symbol)
        
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        
        password1 = request.form.get("password")
        password2 = request.form.get("confirmation")
        username = request.form.get("username")
        
        if not password1 or not username:
            return apology("must provide username and password")

        # Ensure username was submitted
        if not password1 or not password2:
            return apology("must provide password")

        # Ensure password are the same
        if password2 != password1:
            return apology("password must be the same")
        # insert  in the database
        hash_p = generate_password_hash(password1)
        # make sure usename doesn't exist
        try:
            db.execute("insert into users (username, hash) values (?,?)", username, hash_p)
        except ValueError:
            return apology("username already exist")
        except RuntimeError:
            return apology("username already exist")
            
        # Redirect user to home page
        flash("You registred!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # make sure user enter something
        if not (request.form.get('symbol')) or not (request.form.get('shares')):
            return apology("sorry must provide symbol and shares")
        symbol = request.form.get('symbol')
        shares = int(request.form.get('shares'))
        cur_quantity = db.execute("select quantity from history where user_id =:user_id and symbol=:symbol",
                                  user_id=session["user_id"], symbol=symbol)[0]['quantity']
        # check for availible shares
        if shares > cur_quantity:
            return apology("sorry not enough shares")
            
        # calculate the cost
        cost = shares * lookup(request.form.get('symbol'))['price']
        
        # update user cash
        db.execute("update users set cash=cash+:cost where id =:id", cost=cost, id=session["user_id"])
        # update quantity
        db.execute("update history set quantity=quantity-:shares where user_id=:user_id and symbol=:symbol",
                   shares=shares, user_id=session["user_id"], symbol=symbol)
        # insert into transactions
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("insert into all_transactions values(?,?,?,?,?)", 
                   session["user_id"], symbol, - shares, lookup(request.form.get('symbol'))['price'], date)
        
        # redirect to homepage
        flash("Sold!")
        return redirect("/")
        
    rows = db.execute("select symbol from history where user_id=:user_id and quantity > 0", user_id=session["user_id"])
    return render_template("sell.html", rows=rows)


@app.route("/modify", methods=["GET", "POST"])
def modify():
    if request.method == "POST":
        password1 = request.form.get("password")
        password2 = request.form.get("confirmation")
        username = request.form.get("username")
        # make sure username and password exist
        if not username or not password1 or not password2:
            return apology("You must enter username and password")
            
        # query database for username
        if password1 != password2:
            return apology("password must be the same")
        rows = db.execute("SELECT * FROM users where username = ?", username)
        # check if username exist
        if not rows:
            return apology("username doesn't exist register for a new account")
        # generate a new password
        new_pass = generate_password_hash(password1)
        # update the user password
        db.execute('update users set hash = ? where username=?', new_pass, username)
        
        flash("password updated successfully!")
        return redirect(url_for("login"))
            
    return render_template("modify.html")
    
    
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
    
    
# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
