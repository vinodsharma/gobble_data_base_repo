FROM gobble/spark:2.2
ENV APP_DIR=/opt/gobble_data_base_repo
RUN mkdir $APP_DIR
COPY . $APP_DIR/
WORKDIR $APP_DIR
RUN source $VENV_DIR/bin/activate \
  && pip install --upgrade --no-cache-dir -r requirements.txt
