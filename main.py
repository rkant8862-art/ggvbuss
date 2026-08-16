from flask import Flask, request, render_template_string
import math

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Python Calculator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #111827, #1e3a8a);
        }

        .calculator {
            width: 360px;
            padding: 25px;
            border-radius: 25px;
            background: #111827;
            box-shadow: 0 20px 50px rgba(0,0,0,0.45);
        }

        h1 {
            text-align: center;
            color: white;
            margin-top: 0;
            margin-bottom: 20px;
        }

        .display {
            width: 100%;
            min-height: 90px;
            background: #020617;
            color: #38bdf8;
            border-radius: 15px;
            margin-bottom: 18px;
            padding: 15px;
            text-align: right;
            overflow-wrap: anywhere;
        }

        .expression {
            color: #94a3b8;
            font-size: 17px;
            min-height: 25px;
        }

        .result {
            color: #38bdf8;
            font-size: 32px;
            font-weight: bold;
            margin-top: 5px;
        }

        form {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }

        button {
            height: 60px;
            border: none;
            border-radius: 14px;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            background: #334155;
            color: white;
            transition: 0.15s;
        }

        button:hover {
            transform: scale(1.04);
            background: #475569;
        }

        .operator {
            background: #2563eb;
        }

        .operator:hover {
            background: #3b82f6;
        }

        .clear {
            background: #dc2626;
        }

        .equal {
            background: #16a34a;
            grid-column: span 2;
        }

        .function {
            background: #7c3aed;
        }

        .history {
            margin-top: 20px;
            background: #020617;
            border-radius: 15px;
            padding: 15px;
            color: white;
            max-height: 150px;
            overflow-y: auto;
        }

        .history h3 {
            margin-top: 0;
            color: #38bdf8;
        }

        .history-item {
            border-bottom: 1px solid #334155;
            padding: 7px 0;
            font-size: 14px;
        }

        @media(max-width: 420px) {
            .calculator {
                width: 95%;
            }
        }
    </style>
</head>

<body>

<div class="calculator">

    <h1>Python Calculator</h1>

    <div class="display">
        <div class="expression">{{ expression }}</div>
        <div class="result">{{ result }}</div>
    </div>

    <form method="POST">

        <button class="clear" name="value" value="C">C</button>
        <button class="function" name="value" value="sqrt">√</button>
        <button class="function" name="value" value="square">x²</button>
        <button class="operator" name="value" value="/">÷</button>

        <button name="value" value="7">7</button>
        <button name="value" value="8">8</button>
        <button name="value" value="9">9</button>
        <button class="operator" name="value" value="*">×</button>

        <button name="value" value="4">4</button>
        <button name="value" value="5">5</button>
        <button name="value" value="6">6</button>
        <button class="operator" name="value" value="-">−</button>

        <button name="value" value="1">1</button>
        <button name="value" value="2">2</button>
        <button name="value" value="3">3</button>
        <button class="operator" name="value" value="+">+</button>

        <button name="value" value="0">0</button>
        <button name="value" value=".">.</button>
        <button class="equal" name="value" value="=">=</button>

    </form>

    {% if history %}
    <div class="history">
        <h3>History</h3>

        {% for item in history %}
            <div class="history-item">{{ item }}</div>
        {% endfor %}

    </div>
    {% endif %}

</div>

</body>
</html>
"""

expression = ""
result = "0"
history = []


def calculate(exp):
    """
    Safe basic calculator.
    Supports + - * / and decimal numbers.
    """

    allowed = "0123456789+-*/. "

    if not exp:
        return "0"

    if any(char not in allowed for char in exp):
        return "Error"

    try:
        # Prevent invalid operator combinations
        if "**" in exp or "//" in exp:
            return "Error"

        value = eval(exp, {"__builtins__": None}, {})

        if isinstance(value, float):
            if math.isfinite(value):
                if value.is_integer():
                    return str(int(value))
                return str(round(value, 10))

        return str(value)

    except ZeroDivisionError:
        return "Cannot divide by zero"

    except Exception:
        return "Error"


@app.route("/", methods=["GET", "POST"])
def calculator():

    global expression
    global result
    global history

    if request.method == "POST":

        value = request.form.get("value")

        if value == "C":
            expression = ""
            result = "0"

        elif value == "=":

            if expression:

                old_expression = expression
                result = calculate(expression)

                if result not in ["Error", "Cannot divide by zero"]:
                    history.insert(
                        0,
                        old_expression + " = " + result
                    )

                    history = history[:10]

                expression = result

        elif value == "sqrt":

            try:
                number = float(expression)

                if number < 0:
                    result = "Invalid"

                else:
                    result = str(round(math.sqrt(number), 10))
                    history.insert(
                        0,
                        "√" + expression + " = " + result
                    )
                    history = history[:10]
                    expression = result

            except:
                result = "Error"

        elif value == "square":

            try:
                number = float(expression)
                result = str(round(number ** 2, 10))

                history.insert(
                    0,
                    expression + "² = " + result
                )

                history = history[:10]

                expression = result

            except:
                result = "Error"

        else:

            # New number after showing result
            if expression in ["Error", "Cannot divide by zero"]:
                expression = ""

            expression += value

            result = expression

    return render_template_string(
        HTML,
        expression=expression,
        result=result,
        history=history
    )


# if __name__ == "__main__":
#     app.run(
#         host="0.0.0.0",
#         port=5000,
#         debug=True
#     )