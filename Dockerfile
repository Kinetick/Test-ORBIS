FROM python:3.10.8-slim
RUN pip install --upgrade pip
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
STOPSIGNAL SIGINT
CMD [ "python3", "./main.py" ]