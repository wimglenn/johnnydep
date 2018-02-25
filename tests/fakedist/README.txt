To build a wheel for the fakedist:

    pip install --upgrade pip setuptools wheel
    pip wheel --no-deps .


To serve the index (on http://localhost:8000/):

    python3 -m http.server
