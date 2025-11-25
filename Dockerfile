FROM nikolaik/python-nodejs:python3.10-nodejs20

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/
RUN pip install motor
RUN pip3 install --no-cache-dir -U -r requirements.txt

# Install Playwright browsers (Chromium only = lighter)
RUN playwright install chromium \
    && playwright install-deps chromium

# default command
CMD bash start
