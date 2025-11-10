# from repo root
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# run all tests
pytest -q

# run with logs and show snapshot diffs
pytest -vv
