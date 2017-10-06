FROM gobble/python:3.6
ENV APP_DIR=/opt/YOUR_APPLICATION_NAME
RUN mkdir $APP_DIR
COPY . $APP_DIR/
WORKDIR $APP_DIR
RUN source $VENV_DIR/bin/activate \
  && pip install --upgrade --no-cache-dir -r requirements.txt
