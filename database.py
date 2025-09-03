# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных (PostgreSQL/SQLite через SQLAlchemy)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, func, or_, and_
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session, joinedload
from sqlalchemy.exc import IntegrityError
from config import config

Base = declarative_base()

logger = logging.getLogger(__name__)

# Модели базы данных
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)

    # Связи
    created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.creator_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    notifications = relationship("Notification", back_populates="user")
    history_entries = relationship("TaskHistory", back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="check_user_role"),
    )

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assignee_id = Column(Integer, ForeignKey('users.id'))
    status = Column(String(50), nullable=False, default='new')
    priority = Column(String(50), nullable=False, default='medium')
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Связи
    creator = relationship("User", back_populates="created_tasks", foreign_keys=[creator_id])
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    notifications = relationship("Notification", back_populates="task")
    history_entries = relationship("TaskHistory", back_populates="task")

    __table_args__ = (
        CheckConstraint("status IN ('new', 'in_progress', 'completed', 'overdue', 'cancelled')", name="check_task_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="check_task_priority"),
    )

class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    is_sent = Column(Boolean, default=False)
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="notifications")
    task = relationship("Task", back_populates="notifications")

    __table_args__ = (
        CheckConstraint("type IN ('reminder', 'assignment', 'deadline', 'completed')", name="check_notification_type"),
    )

class TaskHistory(Base):
    __tablename__ = 'task_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    action = Column(String(255), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    task = relationship("Task", back_populates="history_entries")
    user = relationship("User", back_populates="history_entries")

class DatabaseManager:
    """Менеджер базы данных для управления задачами"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.get_database_url()
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_database()
    
    def get_db(self) -> Session:
        """Получение сессии базы данных"""
        return self.SessionLocal()

    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("База данных инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    # ПОЛЬЗОВАТЕЛИ
    def create_user(self, telegram_id: int, username: str, first_name: str,
                   last_name: str, role: str) -> bool:
        """Создание нового пользователя"""
        try:
            db = self.get_db()
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Пользователь {username} создан с ролью {role}")
            return True
        except IntegrityError:
            db.rollback()
            logger.warning(f"Пользователь с telegram_id {telegram_id} уже существует")
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при создании пользователя: {e}")
            return False
        finally:
            db.close()
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя по Telegram ID"""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                return {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_active': user.is_active,
                    'registered_at': user.registered_at,
                    'last_activity': user.last_activity
                }
            return None
        finally:
            db.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по внутреннему ID"""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_active': user.is_active,
                    'registered_at': user.registered_at,
                    'last_activity': user.last_activity
                }
            return None
        finally:
            db.close()

    def update_user_activity(self, telegram_id: int):
        """Обновление времени последней активности"""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.last_activity = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def get_all_users(self) -> List[Dict]:
        """Получение всех пользователей"""
        db = self.get_db()
        try:
            users = db.query(User).filter(User.is_active == True).order_by(User.first_name).all()
            return [{
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'is_active': user.is_active,
                'registered_at': user.registered_at,
                'last_activity': user.last_activity
            } for user in users]
        finally:
            db.close()

    def get_users_by_role(self, role: str) -> List[Dict]:
        """Получение пользователей по роли"""
        db = self.get_db()
        try:
            users = db.query(User).filter(User.role == role, User.is_active == True).all()
            return [{
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'is_active': user.is_active,
                'registered_at': user.registered_at,
                'last_activity': user.last_activity
            } for user in users]
        finally:
            db.close()
    
    # ЗАДАЧИ
    def create_task(self, title: str, description: str, creator_id: int,
                   assignee_id: int = None, priority: str = 'medium',
                   deadline: datetime = None) -> int:
        """Создание новой задачи"""
        db = self.get_db()
        try:
            task = Task(
                title=title,
                description=description,
                creator_id=creator_id,
                assignee_id=assignee_id,
                priority=priority,
                deadline=deadline
            )
            db.add(task)
            db.flush()  # Получаем ID без коммита

            # Добавляем запись в историю
            self._add_task_history(db, task.id, creator_id, 'created', None, 'Задача создана')

            db.commit()
            logger.info(f"Задача '{title}' создана с ID {task.id}")
            return task.id
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при создании задачи: {e}")
            raise
        finally:
            db.close()
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """Получение задачи по ID"""
        db = self.get_db()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return None

            creator_name = f"{task.creator.first_name} {task.creator.last_name}" if task.creator else ""
            assignee_name = f"{task.assignee.first_name} {task.assignee.last_name}" if task.assignee else ""
            assignee_telegram_id = task.assignee.telegram_id if task.assignee else None

            return {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'creator_id': task.creator_id,
                'assignee_id': task.assignee_id,
                'status': task.status,
                'priority': task.priority,
                'deadline': task.deadline,
                'created_at': task.created_at,
                'updated_at': task.updated_at,
                'completed_at': task.completed_at,
                'creator_name': creator_name,
                'assignee_name': assignee_name,
                'assignee_telegram_id': assignee_telegram_id
            }
        finally:
            db.close()
    
    def get_tasks_by_user(self, user_id: int, status: str = None) -> List[Dict]:
        """Получение задач пользователя"""
        db = self.get_db()
        try:
            query = db.query(Task).options(
                joinedload(Task.creator),
                joinedload(Task.assignee)
            ).filter(Task.assignee_id == user_id)

            if status:
                query = query.filter(Task.status == status)

            tasks = query.order_by(Task.deadline.asc().nulls_last(), Task.created_at.desc()).all()

            result = []
            for task in tasks:
                creator_name = f"{task.creator.first_name} {task.creator.last_name}" if task.creator else ""
                assignee_name = f"{task.assignee.first_name} {task.assignee.last_name}" if task.assignee else ""

                result.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'creator_id': task.creator_id,
                    'assignee_id': task.assignee_id,
                    'status': task.status,
                    'priority': task.priority,
                    'deadline': task.deadline,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'completed_at': task.completed_at,
                    'creator_name': creator_name,
                    'assignee_name': assignee_name
                })
            return result
        finally:
            db.close()
    
    def get_all_tasks(self, status: str = None, limit: int = None, offset: int = 0) -> List[Dict]:
        """Получение всех задач с пагинацией"""
        db = self.get_db()
        try:
            query = db.query(Task).options(
                joinedload(Task.creator),
                joinedload(Task.assignee)
            )

            if status:
                query = query.filter(Task.status == status)

            if limit:
                query = query.limit(limit).offset(offset)

            tasks = query.order_by(Task.deadline.asc().nulls_last(), Task.created_at.desc()).all()

            result = []
            for task in tasks:
                creator_name = f"{task.creator.first_name} {task.creator.last_name}" if task.creator else ""
                assignee_name = f"{task.assignee.first_name} {task.assignee.last_name}" if task.assignee else ""

                result.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'creator_id': task.creator_id,
                    'assignee_id': task.assignee_id,
                    'status': task.status,
                    'priority': task.priority,
                    'deadline': task.deadline,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'completed_at': task.completed_at,
                    'creator_name': creator_name,
                    'assignee_name': assignee_name
                })
            return result
        finally:
            db.close()

    def update_task_fields(self, task_id: int, updates: Dict, user_id: int) -> bool:
        """Обновление произвольных полей задачи с ведением истории"""
        allowed_fields = {'title', 'description', 'priority', 'deadline', 'assignee_id'}
        changes = {k: v for k, v in updates.items() if k in allowed_fields}
        if not changes:
            return True

        db = self.get_db()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Задача {task_id} не найдена для обновления полей")
                return False

            # Сохраняем старые значения для истории
            for field, value in changes.items():
                old_value = getattr(task, field)
                setattr(task, field, value)

                # Добавляем в историю
                self._add_task_history(db, task_id, user_id, f"{field}_updated", str(old_value) if old_value is not None else None, str(value) if value is not None else None)

            task.updated_at = datetime.utcnow()
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении полей задачи: {e}")
            return False
        finally:
            db.close()

    def search_tasks(self, query_text: str = '', status: Optional[str] = None, priority: Optional[str] = None, assignee_id: Optional[int] = None, creator_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Поиск задач по тексту и фильтрам"""
        db = self.get_db()
        try:
            query = db.query(Task).options(
                joinedload(Task.creator),
                joinedload(Task.assignee)
            )

            # Фильтры
            if query_text:
                search_filter = f"%{query_text}%"
                query = query.filter(or_(
                    Task.title.ilike(search_filter),
                    Task.description.ilike(search_filter)
                ))

            if status:
                query = query.filter(Task.status == status)
            if priority:
                query = query.filter(Task.priority == priority)
            if assignee_id:
                query = query.filter(Task.assignee_id == assignee_id)
            if creator_id:
                query = query.filter(Task.creator_id == creator_id)

            tasks = query.order_by(Task.deadline.asc().nulls_last(), Task.created_at.desc()).limit(limit).offset(offset).all()

            result = []
            for task in tasks:
                creator_name = f"{task.creator.first_name} {task.creator.last_name}" if task.creator else ""
                assignee_name = f"{task.assignee.first_name} {task.assignee.last_name}" if task.assignee else ""

                result.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'creator_id': task.creator_id,
                    'assignee_id': task.assignee_id,
                    'status': task.status,
                    'priority': task.priority,
                    'deadline': task.deadline,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'completed_at': task.completed_at,
                    'creator_name': creator_name,
                    'assignee_name': assignee_name
                })
            return result
        finally:
            db.close()

    def cancel_task(self, task_id: int, user_id: int) -> bool:
        """Отменить задачу (status = cancelled)"""
        db = self.get_db()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Задача {task_id} не найдена для отмены")
                return False

            old_status = task.status
            task.status = 'cancelled'
            task.updated_at = datetime.utcnow()

            self._add_task_history(db, task_id, user_id, 'status_changed', old_status, 'cancelled')

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при отмене задачи: {e}")
            return False
        finally:
            db.close()
    
    def update_task_status(self, task_id: int, status: str, user_id: int) -> bool:
        """Обновление статуса задачи"""
        db = self.get_db()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Задача {task_id} не найдена для обновления статуса")
                return False

            old_status = task.status
            task.status = status
            task.updated_at = datetime.utcnow()

            if status == 'completed':
                task.completed_at = datetime.utcnow()

            # Добавляем в историю
            self._add_task_history(db, task_id, user_id, 'status_changed', old_status, status)

            db.commit()
            logger.info(f"Статус задачи {task_id} изменен на {status}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении статуса задачи: {e}")
            return False
        finally:
            db.close()
    
    def assign_task(self, task_id: int, assignee_id: int, user_id: int) -> bool:
        """Назначение задачи исполнителю"""
        db = self.get_db()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Задача {task_id} не найдена для назначения")
                return False

            old_assignee = task.assignee_id
            task.assignee_id = assignee_id
            task.updated_at = datetime.utcnow()

            # Добавляем в историю
            self._add_task_history(db, task_id, user_id, 'assigned',
                                 str(old_assignee) if old_assignee else None, str(assignee_id))

            db.commit()
            logger.info(f"Задача {task_id} назначена пользователю {assignee_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при назначении задачи: {e}")
            return False
        finally:
            db.close()
    
    def get_overdue_tasks(self) -> List[Dict]:
        """Получение просроченных задач"""
        db = self.get_db()
        try:
            tasks = db.query(Task).options(
                joinedload(Task.creator),
                joinedload(Task.assignee)
            ).filter(
                and_(
                    Task.deadline < datetime.utcnow(),
                    Task.status.not_in(['completed', 'cancelled'])
                )
            ).all()

            result = []
            for task in tasks:
                creator_name = f"{task.creator.first_name} {task.creator.last_name}" if task.creator else ""
                assignee_name = f"{task.assignee.first_name} {task.assignee.last_name}" if task.assignee else ""
                assignee_telegram_id = task.assignee.telegram_id if task.assignee else None

                result.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'creator_id': task.creator_id,
                    'assignee_id': task.assignee_id,
                    'status': task.status,
                    'priority': task.priority,
                    'deadline': task.deadline,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'completed_at': task.completed_at,
                    'creator_name': creator_name,
                    'assignee_name': assignee_name,
                    'assignee_telegram_id': assignee_telegram_id
                })
            return result
        finally:
            db.close()
    
    def update_overdue_tasks(self):
        """Обновление статуса просроченных задач"""
        db = self.get_db()
        try:
            affected = db.query(Task).filter(
                and_(
                    Task.deadline < datetime.utcnow(),
                    Task.status.not_in(['completed', 'cancelled', 'overdue'])
                )
            ).update({
                'status': 'overdue',
                'updated_at': datetime.utcnow()
            })
            db.commit()
            if affected > 0:
                logger.info(f"Обновлено {affected} просроченных задач")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении просроченных задач: {e}")
        finally:
            db.close()
    
    # УВЕДОМЛЕНИЯ
    def create_notification(self, user_id: int, task_id: int, notification_type: str,
                          message: str, scheduled_at: datetime) -> int:
        """Создание уведомления"""
        db = self.get_db()
        try:
            notification = Notification(
                user_id=user_id,
                task_id=task_id,
                type=notification_type,
                message=message,
                scheduled_at=scheduled_at
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            return notification.id
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при создании уведомления: {e}")
            raise
        finally:
            db.close()
    
    def get_pending_notifications(self) -> List[Dict]:
        """Получение неотправленных уведомлений"""
        db = self.get_db()
        try:
            notifications = db.query(Notification).options(
                joinedload(Notification.user),
                joinedload(Notification.task)
            ).filter(
                and_(
                    Notification.is_sent == False,
                    Notification.scheduled_at <= datetime.utcnow()
                )
            ).order_by(Notification.scheduled_at).all()

            result = []
            for notif in notifications:
                result.append({
                    'id': notif.id,
                    'user_id': notif.user_id,
                    'task_id': notif.task_id,
                    'type': notif.type,
                    'message': notif.message,
                    'is_sent': notif.is_sent,
                    'scheduled_at': notif.scheduled_at,
                    'sent_at': notif.sent_at,
                    'created_at': notif.created_at,
                    'telegram_id': notif.user.telegram_id if notif.user else None,
                    'task_title': notif.task.title if notif.task else ""
                })
            return result
        finally:
            db.close()

    def get_unsent_notifications_by_task_type(self, task_id: int, notif_type: str) -> List[Dict]:
        """Получение несент уведомлений по задаче и типу (включая будущие)"""
        db = self.get_db()
        try:
            notifications = db.query(Notification).filter(
                and_(
                    Notification.is_sent == False,
                    Notification.task_id == task_id,
                    Notification.type == notif_type
                )
            ).all()

            return [{
                'id': notif.id,
                'user_id': notif.user_id,
                'task_id': notif.task_id,
                'type': notif.type,
                'message': notif.message,
                'is_sent': notif.is_sent,
                'scheduled_at': notif.scheduled_at,
                'sent_at': notif.sent_at,
                'created_at': notif.created_at
            } for notif in notifications]
        finally:
            db.close()

    def exists_notification_by_task_type(self, task_id: int, notif_type: str) -> bool:
        """Проверка существования уведомления любого статуса для задачи и типа"""
        db = self.get_db()
        try:
            count = db.query(Notification).filter(
                and_(
                    Notification.task_id == task_id,
                    Notification.type == notif_type
                )
            ).count()
            return count > 0
        finally:
            db.close()
    
    def mark_notification_sent(self, notification_id: int):
        """Отметка уведомления как отправленного"""
        db = self.get_db()
        try:
            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if notification:
                notification.is_sent = True
                notification.sent_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    # ИСТОРИЯ
    def _add_task_history(self, db: Session, task_id: int, user_id: int, action: str,
                         old_value: str = None, new_value: str = None):
        """Добавление записи в историю задач"""
        history_entry = TaskHistory(
            task_id=task_id,
            user_id=user_id,
            action=action,
            old_value=old_value,
            new_value=new_value
        )
        db.add(history_entry)

    def get_task_history(self, task_id: int) -> List[Dict]:
        """Получение истории изменений задачи"""
        db = self.get_db()
        try:
            history = db.query(TaskHistory).options(
                joinedload(TaskHistory.user)
            ).filter(TaskHistory.task_id == task_id).order_by(TaskHistory.created_at.desc()).all()

            result = []
            for entry in history:
                user_name = f"{entry.user.first_name} {entry.user.last_name}" if entry.user else ""
                result.append({
                    'id': entry.id,
                    'task_id': entry.task_id,
                    'user_id': entry.user_id,
                    'action': entry.action,
                    'old_value': entry.old_value,
                    'new_value': entry.new_value,
                    'created_at': entry.created_at,
                    'user_name': user_name
                })
            return result
        finally:
            db.close()

    # СТАТИСТИКА
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        db = self.get_db()
        try:
            # Получаем общее количество задач
            total_tasks = db.query(func.count(Task.id)).filter(Task.assignee_id == user_id).scalar() or 0

            # Получаем количество выполненных задач
            completed_tasks = db.query(func.count(Task.id)).filter(
                and_(Task.assignee_id == user_id, Task.status == 'completed')
            ).scalar() or 0

            # Получаем количество просроченных задач
            overdue_tasks = db.query(func.count(Task.id)).filter(
                and_(Task.assignee_id == user_id, Task.status == 'overdue')
            ).scalar() or 0

            # Получаем количество активных задач
            active_tasks = db.query(func.count(Task.id)).filter(
                and_(Task.assignee_id == user_id, Task.status.in_(['new', 'in_progress']))
            ).scalar() or 0

            return {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'overdue_tasks': overdue_tasks,
                'active_tasks': active_tasks
            }
        finally:
            db.close()

    def get_general_stats(self) -> Dict:
        """Получение общей статистики"""
        db = self.get_db()
        try:
            # Общая статистика задач
            total_tasks = db.query(func.count(Task.id)).scalar() or 0
            completed_tasks = db.query(func.count(Task.id)).filter(Task.status == 'completed').scalar() or 0
            overdue_tasks = db.query(func.count(Task.id)).filter(Task.status == 'overdue').scalar() or 0
            active_tasks = db.query(func.count(Task.id)).filter(Task.status.in_(['new', 'in_progress'])).scalar() or 0
            active_users = db.query(func.count(func.distinct(Task.assignee_id))).filter(Task.assignee_id.isnot(None)).scalar() or 0

            # Статистика пользователей
            total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0

            return {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'overdue_tasks': overdue_tasks,
                'active_tasks': active_tasks,
                'active_users': active_users,
                'total_users': total_users
            }
        finally:
            db.close()

# Создаем глобальный экземпляр менеджера БД
db = DatabaseManager()

