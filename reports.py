# -*- coding: utf-8 -*-
"""
Модуль генерации отчётов и диаграмм
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # headless backend for servers/Windows without GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import config, TASK_STATUS, TASK_PRIORITY
from database import db
from utils import format_datetime, get_current_tashkent_time

# Настройка для поддержки русского языка в matplotlib
plt.rcParams['font.family'] = ['DejaVu Sans', 'Liberation Sans', 'Arial Unicode MS']

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Генератор отчётов и диаграмм"""
    
    def __init__(self):
        # Создаём папки для экспорта если их нет
        os.makedirs(config.EXPORT_FOLDER, exist_ok=True)
        os.makedirs(config.CHARTS_FOLDER, exist_ok=True)
    
    def create_excel_report(self, tasks: List[Dict], filename: str = None) -> str:
        """
        Создание Excel отчёта
        
        Args:
            tasks: Список задач
            filename: Имя файла (если не указано, генерируется автоматически)
            
        Returns:
            Путь к созданному файлу
        """
        if not filename:
            timestamp = get_current_tashkent_time().strftime("%Y%m%d_%H%M%S")
            filename = f"task_report_{timestamp}.xlsx"
        
        filepath = os.path.join(config.EXPORT_FOLDER, filename)
        
        # Подготавливаем данные для Excel
        data = []
        for task in tasks:
            row = {
                'ID': task['id'],
                'Название': task['title'],
                'Описание': task['description'] or '',
                'Создатель': task['creator_name'] or '',
                'Исполнитель': task['assignee_name'] or 'Не назначен',
                'Статус': TASK_STATUS[task['status']],
                'Приоритет': TASK_PRIORITY[task['priority']],
                'Дата создания': self._format_date_for_excel(task['created_at']),
                'Дедлайн': self._format_date_for_excel(task['deadline']),
                'Дата выполнения': self._format_date_for_excel(task['completed_at']),
                'Дней на выполнение': self._calculate_completion_days(task),
                'Просрочено': 'Да' if task['status'] == 'overdue' else 'Нет'
            }
            data.append(row)
        
        # Создаём DataFrame
        df = pd.DataFrame(data)
        
        # Создаём Excel файл с несколькими листами
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Основной лист с задачами
            df.to_excel(writer, sheet_name='Задачи', index=False)
            
            # Лист со статистикой
            self._create_statistics_sheet(writer, tasks)
            
            # Лист с аналитикой по пользователям
            self._create_user_analytics_sheet(writer, tasks)
            
            # Форматируем листы
            self._format_excel_sheets(writer)
        
        logger.info(f"Excel отчёт создан: {filepath}")
        return filepath
    
    def create_gantt_chart(self, tasks: List[Dict], filename: str = None) -> str:
        """
        Создание простой и понятной диаграммы Ганта

        Args:
            tasks: Список задач
            filename: Имя файла

        Returns:
            Путь к созданному файлу
        """
        if not filename:
            timestamp = get_current_tashkent_time().strftime("%Y%m%d_%H%M%S")
            filename = f"gantt_chart_{timestamp}.png"

        filepath = os.path.join(config.CHARTS_FOLDER, filename)

        # Фильтруем задачи с дедлайнами
        valid_tasks = [task for task in tasks if task['deadline']]

        if not valid_tasks:
            # Простая пустая диаграмма
            fig, ax = plt.subplots(figsize=(10, 6))

            ax.text(0.5, 0.6, 'Диаграмма Ганта', ha='center', va='center',
                   fontsize=24, fontweight='bold', color='#333333', transform=ax.transAxes)
            ax.text(0.5, 0.4, 'Нет задач с дедлайнами',
                   ha='center', va='center', fontsize=14, color='#666666', transform=ax.transAxes)
            ax.text(0.5, 0.3, 'Создайте задачи с дедлайнами для отображения',
                   ha='center', va='center', fontsize=12, color='#888888', transform=ax.transAxes)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            plt.tight_layout()
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            return filepath

        # Подготавливаем данные
        gantt_data = []
        current_time = get_current_tashkent_time()

        for task in valid_tasks:
            start_date = task['created_at']
            deadline = task['deadline']

            if task['completed_at']:
                end_date = task['completed_at']
            else:
                end_date = min(deadline, current_time)

            gantt_data.append({
                'task': task['title'][:40] + ('...' if len(task['title']) > 40 else ''),
                'start': start_date,
                'end': end_date,
                'deadline': deadline,
                'status': task['status'],
                'assignee': task['assignee_name'] or 'Не назначен',
                'is_overdue': current_time > deadline and not task['completed_at']
            })

        # Сортируем по дедлайну
        gantt_data.sort(key=lambda x: x['deadline'])

        # Создаём диаграмму с оптимизированными размерами
        fig, ax = plt.subplots(figsize=(12, max(5, len(gantt_data) * 0.7)))

        # Цвета для статусов
        colors = {
            'new': '#3498db',        # Синий
            'in_progress': '#f39c12', # Оранжевый
            'completed': '#27ae60',   # Зелёный
            'overdue': '#e74c3c',     # Красный
            'cancelled': '#95a5a6'    # Серый
        }

        y_pos = range(len(gantt_data))

        # Рисуем полосы задач
        for i, task_data in enumerate(gantt_data):
            start = task_data['start']
            end = task_data['end']
            deadline = task_data['deadline']
            status = task_data['status']

            duration = (end - start).total_seconds() / (24*3600)
            color = colors.get(status, '#95a5a6')

            # Преобразуем datetime в числовое значение
            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            deadline_num = mdates.date2num(deadline)

            # Основная полоса задачи с оптимизированной высотой
            ax.barh(i, duration, left=start_num, height=0.8,
                    color=color, alpha=0.8, edgecolor='black', linewidth=1)

            # Дедлайн линия с оптимизированными пропорциями
            if task_data['is_overdue']:
                ax.axvline(x=deadline_num, ymin=(i-0.35)/len(gantt_data), ymax=(i+0.35)/len(gantt_data),
                          color='red', linewidth=2, linestyle='--')
            else:
                ax.axvline(x=deadline_num, ymin=(i-0.35)/len(gantt_data), ymax=(i+0.35)/len(gantt_data),
                          color='orange', linewidth=1.5, linestyle='-.')

            # Название задачи и исполнитель
            task_label = f"{task_data['task']} - {task_data['assignee']}"
            ax.text(start_num + duration + 0.2, i, task_label,
                   ha='left', va='center', fontsize=9, fontweight='medium')

        # Настраиваем оси
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"{i+1}" for i in range(len(gantt_data))])
        ax.invert_yaxis()

        # Форматируем ось времени
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))

        # Поворачиваем подписи дат
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # Заголовок и подписи с уменьшенными отступами
        ax.set_title('Диаграмма Ганта', fontsize=16, fontweight='bold', pad=10)
        ax.set_xlabel('Время', fontsize=11, labelpad=5)
        ax.set_ylabel('Задачи', fontsize=11, labelpad=5)

        # Легенда
        legend_elements = [
            plt.Rectangle((0, 0), 1, 0.5, facecolor=colors['new'], label='Новая'),
            plt.Rectangle((0, 0), 1, 0.5, facecolor=colors['in_progress'], label='В работе'),
            plt.Rectangle((0, 0), 1, 0.5, facecolor=colors['completed'], label='Выполнена'),
            plt.Rectangle((0, 0), 1, 0.5, facecolor=colors['overdue'], label='Просрочена'),
            plt.Line2D([0], [0], color='orange', linewidth=1.5, label='Дедлайн'),
            plt.Line2D([0], [0], color='red', linewidth=2, linestyle='--', label='Просрочен')
        ]
        ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 1.08),
              ncol=3, fontsize=9, frameon=True, fancybox=True)

        # Сетка
        ax.grid(True, alpha=0.3, axis='x')

        # Убираем верхнюю и правую границы
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Текущая дата линия
        current_time_num = mdates.date2num(current_time)
        ax.axvline(x=current_time_num, ymin=0, ymax=1,
                  color='blue', linewidth=1.5, alpha=0.7, linestyle=':')
        # Размещаем текст "Сейчас" внутри области диаграммы
        ax.text(current_time_num, len(gantt_data) - 0.3, 'Сейчас',
               ha='center', va='top', fontsize=9, fontweight='bold',
               bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8, edgecolor='none'))

        # Оптимизируем пространство
        plt.tight_layout()
        plt.subplots_adjust(top=0.85, bottom=0.15, left=0.1, right=0.95)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        logger.info(f"Диаграмма Ганта создана: {filepath}")
        return filepath
    
    def create_user_performance_chart(self, user_id: int = None, filename: str = None) -> str:
        """Создание графика производительности пользователя"""
        if not filename:
            timestamp = get_current_tashkent_time().strftime("%Y%m%d_%H%M%S")
            filename = f"user_performance_{timestamp}.png"
        
        filepath = os.path.join(config.CHARTS_FOLDER, filename)
        
        if user_id:
            # Получаем пользователя по внутреннему ID
            try:
                # добавим вспомогательный метод через обход (получим всех и фильтруем)
                users = [u for u in db.get_all_users() if u['id'] == user_id]
            except Exception:
                users = []
        else:
            users = db.get_all_users()
        
        # Собираем статистику по пользователям
        user_stats = []
        for user in users:
            stats = db.get_user_stats(user['id'])
            stats['name'] = f"{user['first_name']} {user['last_name']}"
            user_stats.append(stats)
        
        if not user_stats:
            return self._create_empty_chart(filepath, "Нет данных о пользователях")
        
        # Создаём график
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        names = [stats['name'] for stats in user_stats]
        
        # График 1: Общее количество задач
        total_tasks = [stats['total_tasks'] for stats in user_stats]
        ax1.bar(names, total_tasks, color='skyblue')
        ax1.set_title('Общее количество задач')
        ax1.set_ylabel('Количество')
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # График 2: Выполненные задачи
        completed_tasks = [stats['completed_tasks'] for stats in user_stats]
        ax2.bar(names, completed_tasks, color='lightgreen')
        ax2.set_title('Выполненные задачи')
        ax2.set_ylabel('Количество')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        # График 3: Процент выполнения
        completion_rates = [
            (stats['completed_tasks'] / max(stats['total_tasks'], 1)) * 100 
            for stats in user_stats
        ]
        ax3.bar(names, completion_rates, color='gold')
        ax3.set_title('Процент выполнения (%)')
        ax3.set_ylabel('Процент')
        ax3.set_ylim(0, 100)
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
        
        # График 4: Просроченные задачи
        overdue_tasks = [stats['overdue_tasks'] for stats in user_stats]
        ax4.bar(names, overdue_tasks, color='salmon')
        ax4.set_title('Просроченные задачи')
        ax4.set_ylabel('Количество')
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        # Оптимизируем для Telegram
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"График производительности создан: {filepath}")
        return filepath
    
    def create_status_distribution_chart(self, tasks: List[Dict], filename: str = None) -> str:
        """Создание круговой диаграммы распределения статусов"""
        if not filename:
            timestamp = get_current_tashkent_time().strftime("%Y%m%d_%H%M%S")
            filename = f"status_distribution_{timestamp}.png"
        
        filepath = os.path.join(config.CHARTS_FOLDER, filename)
        
        # Подсчитываем статусы
        status_counts = {}
        for task in tasks:
            status = task['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if not status_counts:
            return self._create_empty_chart(filepath, "Нет задач для анализа")
        
        # Подготавливаем данные для диаграммы
        labels = [TASK_STATUS[status] for status in status_counts.keys()]
        sizes = list(status_counts.values())
        colors = ['#FFA500', '#4169E1', '#32CD32', '#FF4500', '#808080']
        
        # Создаём круговую диаграмму
        fig, ax = plt.subplots(figsize=(10, 8))
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors[:len(labels)], 
                                         autopct='%1.1f%%', startangle=90)
        
        ax.set_title('Распределение задач по статусам', fontsize=16, fontweight='bold')
        
        # Улучшаем внешний вид
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        plt.tight_layout()
        # Оптимизируем для Telegram
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Диаграмма распределения статусов создана: {filepath}")
        return filepath
    
    def _format_date_for_excel(self, date_str: Optional[str]) -> str:
        """Форматирование даты для Excel"""
        if not date_str:
            return ''
        
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%d.%m.%Y %H:%M')
        except:
            return str(date_str)
    
    def _calculate_completion_days(self, task: Dict) -> str:
        """Расчёт количества дней на выполнение"""
        if not task['completed_at']:
            return ''
        
        try:
            created = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
            completed = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
            days = (completed - created).days
            return str(days)
        except:
            return ''
    
    def _create_statistics_sheet(self, writer, tasks: List[Dict]):
        """Создание листа со статистикой"""
        # Общая статистика
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
        overdue_tasks = len([t for t in tasks if t['status'] == 'overdue'])
        active_tasks = len([t for t in tasks if t['status'] in ['new', 'in_progress']])
        
        # Статистика по приоритетам
        priority_stats = {}
        for priority in TASK_PRIORITY.keys():
            priority_stats[priority] = len([t for t in tasks if t['priority'] == priority])
        
        # Создаём DataFrame со статистикой
        stats_data = [
            ['Общая статистика', ''],
            ['Всего задач', total_tasks],
            ['Выполнено', completed_tasks],
            ['Просрочено', overdue_tasks],
            ['Активных', active_tasks],
            ['Процент выполнения', f"{(completed_tasks/max(total_tasks, 1)*100):.1f}%"],
            ['', ''],
            ['Статистика по приоритетам', ''],
            ['Высокий приоритет', priority_stats.get('high', 0)],
            ['Средний приоритет', priority_stats.get('medium', 0)],
            ['Низкий приоритет', priority_stats.get('low', 0)]
        ]
        
        stats_df = pd.DataFrame(stats_data, columns=['Показатель', 'Значение'])
        stats_df.to_excel(writer, sheet_name='Статистика', index=False)
    
    def _create_user_analytics_sheet(self, writer, tasks: List[Dict]):
        """Создание листа с аналитикой по пользователям"""
        # Группируем задачи по исполнителям
        user_tasks = {}
        for task in tasks:
            assignee = task['assignee_name'] or 'Не назначен'
            if assignee not in user_tasks:
                user_tasks[assignee] = []
            user_tasks[assignee].append(task)
        
        # Создаём статистику по пользователям
        user_analytics = []
        for user, user_task_list in user_tasks.items():
            total = len(user_task_list)
            completed = len([t for t in user_task_list if t['status'] == 'completed'])
            overdue = len([t for t in user_task_list if t['status'] == 'overdue'])
            active = len([t for t in user_task_list if t['status'] in ['new', 'in_progress']])
            
            user_analytics.append({
                'Исполнитель': user,
                'Всего задач': total,
                'Выполнено': completed,
                'Просрочено': overdue,
                'Активных': active,
                'Процент выполнения': f"{(completed/max(total, 1)*100):.1f}%"
            })
        
        analytics_df = pd.DataFrame(user_analytics)
        analytics_df.to_excel(writer, sheet_name='Аналитика по пользователям', index=False)
    
    def _format_excel_sheets(self, writer):
        """Форматирование Excel листов"""
        # Здесь можно добавить форматирование: ширину колонок, цвета, границы и т.д.
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            # Автоподбор ширины колонок
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    def _create_empty_chart(self, filepath: str, message: str) -> str:
        """Создание пустой диаграммы с сообщением"""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, message, ha='center', va='center', 
               fontsize=16, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        plt.tight_layout()
        # Оптимизируем для Telegram
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        return filepath

