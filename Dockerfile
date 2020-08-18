FROM heroku/heroku:18-build
RUN python3 -m pip install -r requirements.txt
ADD . .
CMD python3 EU4Bot.py