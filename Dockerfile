FROM heroku/heroku:18-build
RUN sudo apt-get install python3-dev
ADD . .
ADD https://bootstrap.pypa.io/get-pip.py get-pip.py
RUN python3 get-pip.py
RUN rm get-pip.py
RUN pip install -r requirements.txt
CMD python3 EU4Bot.py