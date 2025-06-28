# === Builder Stage ===
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build-Zeit Argumente (nur für collectstatic etc.)
ARG SECRET_KEY
ARG DOCKER=True
ARG DB_NAME
ARG DB_USER
ARG DB_PASSWORT
ARG DB_HOST
ARG DB_PORT=5432

# System Dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        libjpeg-dev \
        libopenjp2-7-dev \
        curl \
        apt-transport-https \
        lsb-release \
        ca-certificates \
        jq \
        gnupg \
        # WeasyPrint Dependencies
        libpango-1.0-0 \
        libharfbuzz0b \
        libpangoft2-1.0-0 \
        libfontconfig1 \
        libcairo2 \
        libgdk-pixbuf2.0-0 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        unixodbc \
        unixodbc-dev \
    # Add Microsoft repository and install ODBC driver
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python Dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Temporäre ENV für Build-Prozesse (collectstatic)
ENV SECRET_KEY=$SECRET_KEY
ENV DOCKER=$DOCKER
ENV DB_NAME=$DB_NAME
ENV DB_USER=$DB_USER
ENV DB_PASSWORT=$DB_PASSWORT
ENV DB_HOST=$DB_HOST
ENV DB_PORT=$DB_PORT

# Build-Zeit Aufgaben
RUN python manage.py collectstatic --noinput

# === Final Stage ===
FROM python:3.12-slim-bookworm

ENV FONTCONFIG_PATH=/tmp/fontconfig
RUN mkdir -p /tmp/fontconfig && chmod -R 777 /tmp/fontconfig
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Runtime Dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        libffi-dev \
        libjpeg-dev \
        libopenjp2-7-dev \
        curl \
        apt-transport-https \
        gnupg \
        # WeasyPrint Runtime Dependencies
        libpango-1.0-0 \
        libharfbuzz0b \
        libpangoft2-1.0-0 \
        libfontconfig1 \
        libcairo2 \
        libgdk-pixbuf2.0-0 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        unixodbc \
        unixodbc-dev \
        ffmpeg \
    # Add Microsoft repository and install ODBC driver
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopiere aus Builder Stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

CMD ["uvicorn", "FCCSemesterAufgabe.asgi:application", "--host", "0.0.0.0", "--port", "8000"]


EXPOSE 8000
