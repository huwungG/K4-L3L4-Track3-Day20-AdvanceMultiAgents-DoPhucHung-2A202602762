# TÙY CHỌN: chạy lab trong container để shell của tác tử không chạm vào máy chủ của bạn.
# Build:  docker build -t lab-deepagents .
# Run:    docker run --rm -it --env-file .env -v "$PWD":/lab lab-deepagents
FROM python:3.12-slim
WORKDIR /lab
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
# PANDAS cho tác vụ data-*: các tác vụ CSV cần thư viện này.
RUN pip install --no-cache-dir pandas
CMD ["bash"]
