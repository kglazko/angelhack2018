"""
This sample demonstrates an implementation of the Lex Code Hook Interface
in order to serve a sample bot which manages reservations for hotel rooms and car rentals.
Bot, Intent, and Slot models which are compatible with this sample can be found in the Lex Console
as part of the 'BookTrip' template.

For instructions on how to set up and test this bot, as well as additional samples,
visit the Lex Getting Started documentation http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.
"""

import json
import logging
import os
import time

from sqlalchemy import create_engine, Column, Integer, Sequence, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_USERNAME = os.environ.get("DATABASE_USERNAME")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")


engine = create_engine('mysql+pymysql://{}:{}@{}/homeless'.format(DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_HOST), pool_recycle=3600)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    first_name = Column(String(32))
    last_name = Column(String(32))
    phone_number = Column(String(14))  # TODO: optimize key on phone_number

Base.metadata.create_all(engine)

# --- Helpers that build all of the responses ---

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close_empty(session_attributes, fulfillment_state):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': {
                "contentType": "PlainText",
                "content": message,
            }
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

def elicit_intent(session_attributes, message=None):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitIntent',
        }
    }
    if message is not None:
        response['dialogAction']['message'] = {
            'contentType': 'PlainText',
            'content': message,
        }
    return response

def onboarding(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    phone_number = intent_request['userId']

    session = Session()
    user = session.query(User).filter_by(phone_number=phone_number).one_or_none()
    if user is not None:
        return elicit_intent(session_attributes, message="Welcome back {}! If you want to apply to jobs type job.".format(user.first_name))

    if intent_request['currentIntent']['slots']['wants_to_enroll'] == 'No':
        # user does not want to enroll
        return close(session_attributes, "Fulfilled",
                     "When you're ready, we'll be here for you.")
    if all(intent_request['currentIntent']['slots'].values()):
        # all user inputs filled out
        first_name = intent_request['currentIntent']['slots']['first_name']
        last_name = intent_request['currentIntent']['slots']['last_name']
        new_user = User(first_name=first_name, last_name=last_name, phone_number=phone_number)
        session.add(new_user)
        session.commit()
        return close_empty(session_attributes, "Fulfilled")
    return delegate(session_attributes, intent_request['currentIntent']['slots'])


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.error(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'Onboard':
        return onboarding(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    # return {
    #   "sessionAttributes": {
    #   },
    #   "dialogAction": {
    #     "type": "Delegate",
    #     "slots": {
    #       "wants_to_enroll": None,
    #       "last_name": None,
    #       "first_name": None,
    #     },
    #   }
    # }

    return dispatch(event)
