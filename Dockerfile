FROM heroku/heroku:18-build
ADD . .
CMD python EU4Bot.py