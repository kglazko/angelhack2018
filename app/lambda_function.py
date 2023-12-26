import json
import logging
import os
import time
from collections import namedtuple

import boto3
import requests
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

def search_darcel(query):
    DarcelLink = namedtuple('DarcelLink', ['name', 'url'])
    url_str = 'https://askdarcel.org/resource?id={}'
    darcel_resources = json.loads(requests.get('https://askdarcel.org/api/resources/search?lat=37.7749&long=-122.4194&query={}'.format(query)).content)['resources']
    return [DarcelLink(name=x['name'], url=url_str.format(x['id'])) for x in darcel_resources]


def start_fargate(email, zip, position, password):
    session = boto3.session.Session()
    client = session.client('ecs')
    client.run_task(
        cluster='default',
        taskDefinition='autoindeed:1',
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [
                    'subnet-dbe96fd4',
                ],
                'securityGroups': [
                    'sg-0a99a043'
                ],
            }
        },
        overrides={
            'taskRoleArn': 'arn:aws:iam::436052868155:role/ecsTaskExecutionRole',
            'containerOverrides': [
                {
                    'name': 'indeed',
                    'environment': [
                        {
                            'name': 'EMAIL_ADDRESS',
                            'value': email,
                        },
                        {
                            'name': 'ZIP',
                            'value': zip,
                        },
                        {
                            'name': 'POSITION',
                            'value': position,
                        },
                        {
                            'name': 'PASSWORD',
                            'value': password,
                        },
                        {
                            'name': 'SELENIUM_DRIVER_HOSTNAME',
                            'value': '127.0.0.1',
                        }
                    ]
                }
            ]
        }
    )

def indeed(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    phone_number = intent_request['userId']

    session = Session()
    if (user := session.query(User).filter_by(phone_number=phone_number).one_or_none()) is None:
        return elicit_intent(session_attributes, message="Please register first. Type register")

    if all(intent_request['currentIntent']['slots'].values()):
        email_address = intent_request['currentIntent']['slots']['email_address']
        zip = intent_request['currentIntent']['slots']['zip']
        password = intent_request['currentIntent']['slots']['password']
        position = intent_request['currentIntent']['slots']['position']
        try:
            start_fargate(email_address, zip, position, password)
        except Exception as e:  # TODO: remove on good test
            return elicit_intent(session_attributes,
                                 message=e.message)
        return elicit_intent(session_attributes, message="You have been put in the queue for automatic job applications. Application confirmation emails for {} will arrive shortly to {}. Good luck!".format(position, email_address))
    return delegate(session_attributes, intent_request['currentIntent']['slots'])


def onboarding(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    phone_number = intent_request['userId']

    session = Session()
    if (user := session.query(User).filter_by(phone_number=phone_number).one_or_none()) is not None:
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

def darcel(intent_request, query):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    result = search_darcel(query)[0:5]
    result_str = '\n'.join('{}: {}'.format(r.name, r.url) for r in result)
    return close(session_attributes, "Fulfilled",
                 "Here are some results:\n{}".format(result_str))


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.error(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))


    # Dispatch to your bot's intent handlers
    if (intent_name := intent_request['currentIntent']['name']) == 'Onboard':
        return onboarding(intent_request)
    if intent_name == 'LinkedIn':
        return indeed(intent_request)
    if intent_name == 'DarcelHousing':
        return darcel(intent_request, 'housing')
    if intent_name == 'DarcelFood':
        return darcel(intent_request, 'food')

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

