FROM python:3.11-slim

WORKDIR /app
COPY req.txt .
RUN pip install -r req.txt

COPY . .
EXPOSE 8080

CMD ["python", "app.py"]
