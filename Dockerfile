FROM python:3.11.2
ADD . .
RUN pip3 install -r requirements.txt
CMD python3 -u EU4Bot.py