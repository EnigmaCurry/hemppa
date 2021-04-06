import urllib.request
import wolframalpha
from html import escape
from modules.common.module import BotModule


class MatrixModule(BotModule):
    app_id = ''

    def matrix_start(self, bot):
        super().matrix_start(bot)
        self.add_module_aliases(bot, ['wafull'])

    async def matrix_message(self, bot, room, event):
        args = event.body.split()
        if len(args) == 3:
            if args[1] == "appid":
                bot.must_be_owner(event)
                self.app_id = args[2]
                bot.save_settings()
                await bot.send_text(room, 'App id set')
                return

        if len(args) > 1:
            if self.app_id == '':
                await bot.send_text(room, 'Please get and set a appid: https://products.wolframalpha.com/simple-api/documentation/')
                return

            query = event.body[len(args[0])+1:]
            client = wolframalpha.Client(self.app_id)
            res = client.query(query)
            result = "?SYNTAX ERROR"
            if res['@success']:
                self.logger.debug(f"room: {room.name} sender: {event.sender} sent a valid query to wa")
            else:
                self.logger.info(f"wa error: {res['@error']}")
            short, full = self.parse_api_response(res)
            if full[0] and 'full' in args[0]:
                html, plain = full
            elif short[0]:
                html, plain = short
            else:
                print(short)
                plain = 'Could not find response for ' + query
                html = plain
            await bot.send_html(room, html, plain)
        else:
            await bot.send_text(room, 'Usage: !wa <query>')

    def get_settings(self):
        data = super().get_settings()
        data['app_id'] = self.app_id
        return data

    def set_settings(self, data):
        super().set_settings(data)
        if data.get("app_id"):
            self.app_id = data["app_id"]

    def parse_api_response(self, res):
        """Parses the pods from wa and prepares texts to send to matrix

        :param res: the result from wolframalpha.Client
        :type res: dict
        :return: a tuple of tuples: ((primary_html, primary_plaintext), (full_html, full_plaintext))
        :rtype: tuple
        """
        htmls = []
        texts = []
        primary = None
        fallback = None

        # workaround for bug(?) in upstream wa package
        if hasattr(res['pod'], 'get'):
            res['pod'] = [res['pod']]
        for pod in res['pod']:
            pod_htmls = []
            pod_texts = []
            spods = pod.get('subpod')
            if not spods:
                continue

            # workaround for bug(?) in upstream wa package
            if hasattr(spods, 'get'):
                spods = [spods]
            for spod in spods:
                title = spod.get('@title')
                text  = spod.get('plaintext')
                if not text:
                    continue

                if title:
                    html = f'<strong>{escape(title)}</strong>: {escape(text)}'
                    text = f'title: text'
                else:
                    html  = escape(text)
                    plain = text
                pod_htmls += [f'<li>{s}</li>' for s in html.split('\n')]
                pod_texts += [f'- {s}'        for s in text.split('\n')]

            if pod_texts:
                title = pod.get('@title')
                pod_html = '\n'.join([f'<p><strong>{escape(title)}</strong>\n<ul>'] + pod_htmls + ['</ul></p>'])
                pod_text = '\n'.join([title] + pod_texts)
                htmls.append(pod_html)
                texts.append(pod_text)
                if not primary and self.is_primary(pod):
                    primary = (pod_html, pod_text)
                else:
                    fallback = fallback or (pod_html, pod_text)

        return (primary or fallback, ('\n'.join(htmls), '\n'.join(texts)))

    def is_primary(self, pod):
        return pod.get('@primary') or 'Definition' in pod.get('@title') or 'Result' in pod.get('@title')

    def help(self):
        return ('Wolfram Alpha search')
