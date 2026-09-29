from aiohttp import web
from navconfig import config

app = web.Application()

print('ENV > ', config.get('ENV'))

async def ping(request):
    return web.Response(text='pong')

async def home(request):
    return web.Response(text='Hello, World!')


# Add routes for the home and ping endpoints
app.router.add_get('/', home)
app.router.add_get('/ping', ping)


# Run the application
if __name__ == '__main__':
    web.run_app(
        app,
        host=config.get('HOST', '0.0.0.0'),
        port=config.getint('PORT', fallback=9090)
    )
