FROM heroku/heroku:18-build
COPY https://bootstrap.pypa.io/get-pip.py get-pip.py
RUN python3 get-pip.py
RUN rm get-pip.py
RUN pip install -r requirements.txt
ADD . .
CMD python3 EU4Bot.py