python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py migrate app

exec python3 -u manage.py runserver 0.0.0.0:8000