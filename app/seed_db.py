from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.database import get_db, Base, engine
from app.models import User, ArticleType
from app.schemas import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_database():
    Base.metadata.create_all(bind=engine)
    
    db = next(get_db())
    
    # 检查是否已存在用户
    if not db.query(User).filter(User.username == "pan").first():
        # 创建管理员用户
        admin_user = User(
            username="pan",
            hashed_password=pwd_context.hash("password123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    
    # 检查是否已存在文章类型
    if not db.query(ArticleType).filter(ArticleType.name == "毕业论文").first():
        # 创建文章类型
        article_type = ArticleType(
            name="毕业论文",
            is_public=True,
            prompt='''
#论文标准
## 论文内容要求
* 具体的项目描述（需求分析）：
  - 项目背景，使用环境，要解决的问题：有参数，要定量；
* 相关理论知识的简单介绍（解决问题的思路）；
* 利用有关理论解决问题的过程：重点论述"为什么"，而不是"是什么"
* 最终设计成果展示：能运行的软件，硬件或系统照片，模拟运行截图，可操作的设计方案等
* 项目总结：心得、未尽事宜、改进方案、自我评估、闪光点等
* 附录：参考文献，源代码，电路图等

## 评判标准
* 未有具体的设计内容/基本要求未达到 -- 不及格
* 有设计结果没有设计过程（缺乏中间文档，计算，设计结果没有数据支撑）-- 及格
* 有设计过程及设计结果展示，设计过程有逻辑性，可自圆其说，可以有小瑕疵 -- 良好
* 设计工作量大，有真正应用价值，个人逻辑清楚，查重小于10% -- 优秀

根据这个论文标准评价一下这篇论文
''',
            owner_id=1  # 假设admin用户的ID为1
        )
        db.add(article_type)
        db.commit()
    
    db.close()

if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully!")