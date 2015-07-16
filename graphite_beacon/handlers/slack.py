import json
from slacker import Slacker
import requests
from tornado import gen, httpclient as hc

from . import AbstractHandler, LOGGER
from ..template import TEMPLATES


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
        rule = kwargs['rule']
        # message = self.get_message(level, alert, value, **kwargs)

        image_url = alert.get_attachment_url()
        uploaded_url = self.post_image(image_url)

        self.slack.chat.post_message(
            self.channel_id,
            text='',
            username=self.username,
            icon_emoji=self.emoji.get(level, ':warning:'),
            attachments=[{
                'title': 'Graphite-beacon alert',
                # 'title_link': image_urln,
                'image_url': uploaded_url,
                'color': self.colors[level],
                'fields': [
                    {
                        'title': 'Alert Triggered',
                        'value': "<{0}|{1}>".format(image_url, alert.name),
                        'short': False
                    },
                    { 'title': 'Target', 'value': target, 'short': False },
                    { 'title': 'Rule', 'value': rule['raw'], 'short': True },
                    { 'title': 'Value', 'value': alert.convert(value), 'short': True },
                ]
            }]
        )
        return True

        # data = dict()
        # data['username'] = self.username
        # data['text'] = message
        # data['icon_emoji'] = self.emoji.get(level, ':warning:')
        # if self.channel:
        #     data['channel'] = self.channel
        # alert = args[0]
        # value = args[1]

        # data['attachments'] = [{
        #     'image_url': image_url,
        #     'color': self.colors[level],
        #     'title': alert.name,
        #     'title_link': url,
        #     'fields': [
        #         {
        #             "title": "Rule",
        #             "value": rule['raw'],
        #             "short": False,
        #         },
        #         {
        #             "title": "Target",
        #             "value": target,
        #             "short": False,
        #         },
        #         {
        #             "title": "Value",
        #             "value": alert.convert(value),
        #             "short": True
        #         },
        #         {
        #             "title": "Level",
        #             "value": level.title(),
        #             "short": True
        #         },
        #     ]
        # }]

        # {
        #     "attachments": [
        #         {
        #             "fallback": "Network traffic (kb/s): How does this look? @slack-ops - Sent by Julie Dodd - https://datadog.com/path/to/event",
        #             "title": "Network traffic (kb/s)",
        #             "title_link": "https://datadog.com/path/to/event",
        #             "text": "How does this look? @slack-ops - Sent by Julie Dodd",
        #             "image_url": "https://datadoghq.com/snapshot/path/to/snapshot.png",
        #             "color": "#764FA5"
        #         }
        #     ]
        # }

        # body = json.dumps(data)
        # slack.chat.post_message(self.channel, '', attachments=)
        # yield self.client.fetch(self.webhook, method='POST', body=body)
