import json
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
        self.webhook = self.options.get('webhook')
        assert self.webhook, 'Slack webhook is not defined.'

        self.channel = self.options.get('channel')
        if self.channel and not self.channel.startswith('#'):
            self.channel = '#' + self.channel
        self.username = self.options.get('username')
        self.client = hc.AsyncHTTPClient()

    def get_message(self, level, alert, value, target=None, ntype=None, rule=None):
        msg_type = 'slack' if ntype == 'graphite' else 'short'
        tmpl = TEMPLATES[ntype][msg_type]
        return tmpl.generate(
            level=level, reactor=self.reactor, alert=alert, value=value, target=target).strip()

    @gen.coroutine
    def notify(self, level, alert, value, **kwargs):
        LOGGER.debug("Handler (%s) %s", self.name, level)

        message = self.get_message(level, alert, value, **kwargs)
        data = dict()
        data['username'] = self.username
        # data['text'] = message
        data['icon_emoji'] = self.emoji.get(level, ':warning:')
        if self.channel:
            data['channel'] = self.channel
        # alert = args[0]
        # value = args[1]
        target = kwargs['target']
        rule = kwargs['rule']
        url = alert.get_attachment_url(target)
        colors = {
            'crit'
        }
        data['attachments'] = [{
            'image_url': url,
            # 'color': "#39C",
            'color': self.colors[level],
            # 'text': "Alert is now at {}".format(level),
            'title': alert.name,
            'title_link': url,
            'fields': [
                {
                    "title": "Rule",
                    "value": rule['raw'],
                    "short": False,
                },
                {
                    "title": "Target",
                    "value": target,
                    "short": False,
                },
                {
                    "title": "Value",
                    "value": alert.convert(value),
                    "short": True
                },
                {
                    "title": "Level",
                    "value": level,
                    "short": True
                },
            ]
        }]
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

        body = json.dumps(data)
        yield self.client.fetch(self.webhook, method='POST', body=body)
