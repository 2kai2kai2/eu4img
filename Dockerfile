FROM heroku/heroku:18-build
RUN apt-get update
RUN apt-get -y --force-yes install python3-dev python3-pip
ADD . .
RUN pip3 install -r requirements.txt
CMD python3 -u EU4Bot.py