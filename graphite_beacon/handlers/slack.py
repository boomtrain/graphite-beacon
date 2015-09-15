from slacker import Slacker
import requests
from tornado import httpclient as hc

from . import AbstractHandler, LOGGER
from ..template import TEMPLATES

INTERNAL_ERRORS = (
    'loading',
    'waiting',
)

class SlackHandler(AbstractHandler):

    name = 'slack'

    # Default options
    defaults = {
        'webhook': None,
        'channel': None,
        'username': 'graphite-beacon',
    }

    colors = {
        'critical': '#dc322f',
        'warning': '#b58900',
        'normal': '#859900',
    }

    emoji = {
        'critical': ':exclamation:',
        'warning': ':warning:',
        'normal': ':white_check_mark:',
    }

    def init_handler(self):
        self.token = self.options.get('token')
        assert self.token, 'Slack api token is not defined.'
        self.slack = Slacker(self.token)

        self.channel = self.options.get('channel')
        self.channel_id = self.slack.channels.get_channel_id(self.channel)
        # if self.channel and self.channel[0] not in ('#', '@'):
        #     self.channel = '#' + self.channel
        self.username = self.options.get('username')
        self.client = hc.AsyncHTTPClient()

    def get_message(self, level, alert, value, target=None, ntype=None, rule=None):
        msg_type = 'slack' if ntype == 'graphite' else 'short'
        tmpl = TEMPLATES[ntype][msg_type]
        return tmpl.generate(
            level=level, reactor=self.reactor, alert=alert, value=value, target=target).strip()

    def post_image(self, url):
        d = requests.get(url)
        if d.status_code != 200:
            return None
        r = self.slack.files.post(
            'files.upload',
            files={'file': d.content},
            params={'filename':'graphite-beacon'},
        )
        return r.body['file']['url']

    # @gen.coroutine
    def notify(self, level, alert, value, **kwargs):
        LOGGER.debug("Handler (%s) %s", self.name, level)

        target = kwargs['target']
        # message = self.get_message(level, alert, value, **kwargs)

        image_url = alert.get_attachment_url(target)
        uploaded_url = self.post_image(image_url)
        try:
            rule = kwargs['rule']['raw']
        except (KeyError, TypeError):
            rule = 'N/A'

        if target in INTERNAL_ERRORS:
            attachment = {
                'color': self.colors[level],
                'fields': [
                    {
                        'title': 'Monitoring Error',
                        'value': value,
                        'short': False
                    },
                    {
                        'title': 'Target',
                        'value': alert.name,
                        'short': False
                    },
                ]
            }
        elif level == 'normal':
            attachment = {
                'image_url': uploaded_url,
                'color': self.colors[level],
                'fields': [
                    {
                        'title': 'Alert Cleared',
                        'value': "<{0}|{1}>".format(image_url, alert.name),
                        'short': False
                    },
                    {'title': 'Target', 'value': target, 'short': False},
                    {'title': 'Rule', 'value': 'Cleared', 'short': True},
                    {'title': 'Value', 'value': alert.convert(value), 'short': True},
                ]
            }
        else:
            attachment = {
                'image_url': uploaded_url,
                'color': self.colors[level],
                'fields': [
                    {
                        'title': 'Alert Triggered',
                        'value': "<{0}|{1}>".format(image_url, alert.name),
                        'short': False
                    },
                    {'title': 'Target', 'value': target, 'short': False},
                    {'title': 'Rule', 'value': rule, 'short': True},
                    {'title': 'Value', 'value': alert.convert(value), 'short': True},
                ]
            }

        self.slack.chat.post_message(
            self.channel_id,
            text='',
            username=self.username,
            icon_emoji=self.emoji.get(level, ':warning:'),
            attachments=[attachment]
        )
        return True
