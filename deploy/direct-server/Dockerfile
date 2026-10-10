FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
WORKDIR /app
COPY requirements-server.txt /app/
RUN pip install --no-cache-dir -r requirements-server.txt && useradd --uid 10001 --create-home doll && mkdir /data && chown doll:doll /data
COPY tools /app/tools
USER doll
EXPOSE 8781
CMD ["python", "tools/direct_server.py", "--listen", "0.0.0.0", "--port", "8781", "--data-dir", "/data"]
