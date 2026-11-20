# VideoclubAPPV

Console application (Python + SQLite) to manage video clubs, movies, members, rentals and monthly statistics.

## Files
- `app.py` – application code (classes and menu)
- `schema.sql` – database schema
- `test_app.py` – automated tests (41 tests)
- `diagrama_clases.puml` / `diagrama_clases.png` – class diagram
- `Informe_VideoclubAPPV.pdf` – project report

## Run
```
python app.py
```

## Tests and coverage
```
python -m unittest -v
python -m coverage run --source=. --omit=test_app.py -m unittest
python -m coverage report
```

Code quality is analyzed with SonarQube.
