"""Dispatch alerts via Slack."""
from slacker import Slacker
import requests
from tornado import httpclient as hc

from . import AbstractHandler, LOGGER

INTERNAL_ERRORS = (
    'loading',
    'waiting',
)
INTERNAL_RECOVERY = (
    'Metrics are loaded',
)
BOT_CHANNEL = '#bot_files'


class SlackHandler(AbstractHandler):

    """Dispatch alerts via Slack."""

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
        'internal': '#6c71c4',
        'internal_good': '#268bd2',
    }

    emoji = {
        'critical': ':exclamation:',
        'warning': ':warning:',
        'normal': ':white_check_mark:',
        'internal': ':broken_heart:',
        'internal_good': ':heart:',
    }

    def init_handler(self):
        """Startup initialization for Slack."""
        self.token = self.options.get('token')
        assert self.token, 'Slack api token is not defined.'
        self.slack = Slacker(self.token)
        self.username = self.options.get('username')
        self.client = hc.AsyncHTTPClient()

    def post_image(self, url):
        """Post an image to Slack so it can be attached to a message."""
        d = requests.get(url)
        if d.status_code != 200:
            return None
        r = self.slack.files.post(
            'files.upload',
            files={'file': d.content},
            params={
                'filename': 'graphite-beacon.png',
                'filetype': 'png',
                'channels': BOT_CHANNEL,
            },
        )
        try:
            url = r.body['file']['url_private']
            LOGGER.info("Posted URL: %s", url)
            return url
        except KeyError:
            LOGGER.error("Unable to get URL for image: %r", r)
            return None

    # @gen.coroutine
    def notify(self, level, alert, value, **kwargs):
        LOGGER.debug("Handler (%s) %s", self.name, level)

        target = kwargs['target']

        image_url = alert.get_attachment_url(target)
        try:
            rule = kwargs['rule']['raw']
        except (KeyError, TypeError):
            rule = 'N/A'

        # Allow for overridable channel per-rule.

        if alert.channel:
            channel = alert.channel
        else:
            channel = self.options.get('channel')

        # For the lazy. (i.e. Me.)
        def _short(title, value):
            return {'title': title, 'value': value, 'short': True}

        def _long(title, value):
            return {'title': title, 'value': value, 'short': False}

        if target in INTERNAL_ERRORS:
            if value in INTERNAL_RECOVERY:
                level = 'internal_good'
            else:
                level = 'internal'
            attachment = {
                'color': self.colors[level],
                'fields': [
                    _long('Monitoring Error', value),
                    _long('Target', alert.name),
                ]
            }
        elif level == 'normal':
            attachment = {
                'image_url': self.post_image(image_url),
                'color': self.colors[level],
                'fields': [
                    _long('Alert Cleared', alert.name),
                    _long('Target', target),
                    _short('Rule', 'Cleared'),
                    _short('Value', alert.convert(value)),
                ]
            }
        else:
            attachment = {
                'image_url': self.post_image(image_url),
                'color': self.colors[level],
                'fields': [
                    _long('Alert Triggered', alert.name),
                    _long('Target', target),
                    _short('Rule', rule),
                    _short('Value', alert.convert(value)),
                ]
            }

        channel_id = self.slack.channels.get_channel_id(channel)
        LOGGER.info("Posting message with attachment: %r", attachment)
        self.slack.chat.post_message(
            channel_id,
            text='',
            username=self.username,
            icon_emoji=self.emoji.get(level, ':warning:'),
            attachments=[attachment]
        )
        return True
