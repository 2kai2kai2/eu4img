FROM heroku/heroku:18-build
ADD . .
CMD python3 EU4Bot.py