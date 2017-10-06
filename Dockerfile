FROM gobble/python:3.6_spark_2.2
ENV APP_DIR=/opt/your_application_name
RUN mkdir $APP_DIR
COPY . $APP_DIR/
WORKDIR $APP_DIR
RUN source $VENV_DIR/bin/activate \
  && pip install --upgrade --no-cache-dir -r requirements.txt
