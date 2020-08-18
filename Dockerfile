FROM heroku/heroku:18-build
ADD . .
CMD python app/EU4Bot.py