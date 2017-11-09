FROM gobble/spark:2.2
ENV APP_DIR=/opt/YOUR_GITHUB_REPO_NAME
RUN mkdir $APP_DIR
COPY . $APP_DIR/
WORKDIR $APP_DIR
RUN source $VENV_DIR/bin/activate \
  && pip install --upgrade --no-cache-dir -r requirements.txt
