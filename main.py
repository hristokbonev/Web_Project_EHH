from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
# from routers.admin import router as admin_router
from common.exceptions import BadRequestException, ForbiddenException, UnauthorizedException
from routers.api.users import users_router
from routers.api.categories import router as categories_router
from routers.api.messages import messages_router
from routers.api.replies import router as replies_router
from routers.api.topics import topics_router
# from routers.votes import router as votes_router
from routers.web.categories import router as web_categories_router
# from routers.web.messages import router as web_messages_router
from routers.web.replies import router as web_replies_router
from routers.web.home import router as home_router
# from routers.web.topics import router as web_topics_router
from routers.web.users import router as web_users_router
from common.template_config import CustomJinja2Templates

import uvicorn

app = FastAPI()
templates = CustomJinja2Templates(directory="templates")

# app.include_router(admin_router)
app.include_router(users_router)
app.include_router(home_router)
app.include_router(categories_router)
app.include_router(messages_router)
app.include_router(replies_router)
app.include_router(topics_router)
# app.include_router(votes_router)
app.include_router(web_categories_router)
# app.include_router(web_messages_router)
app.include_router(web_replies_router)
# app.include_router(web_topics_router)
app.include_router(web_users_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)