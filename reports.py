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
        Создание премиум диаграммы Ганта с улучшенным дизайном

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
            # Создаём красивую пустую диаграмму
            fig, ax = plt.subplots(figsize=(16, 8), facecolor='#f8f9fa')

            # Градиентный фон
            gradient = plt.matplotlib.colors.LinearSegmentedColormap.from_list("", ["#667eea", "#764ba2"])
            ax.imshow([[0, 0], [1, 1]], extent=[0, 1, 0, 1], aspect='auto',
                      cmap=gradient, alpha=0.1, transform=ax.transAxes)

            # Иконка и текст
            ax.text(0.5, 0.6, '📊', ha='center', va='center', fontsize=64, transform=ax.transAxes)
            ax.text(0.5, 0.45, 'Диаграмма Ганта', ha='center', va='center',
                   fontsize=28, fontweight='bold', color='#2c3e50', transform=ax.transAxes)
            ax.text(0.5, 0.35, 'Нет задач с дедлайнами для отображения',
                   ha='center', va='center', fontsize=16, color='#7f8c8d', transform=ax.transAxes)
            ax.text(0.5, 0.25, 'Создайте задачи с дедлайнами, чтобы увидеть график',
                   ha='center', va='center', fontsize=14, color='#95a5a6', transform=ax.transAxes)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='#f8f9fa')
            plt.close()
            return filepath

        # Подготавливаем данные с дополнительными метриками
        gantt_data = []
        current_time = get_current_tashkent_time()

        for task in valid_tasks:
            start_date = task['created_at']
            deadline = task['deadline']

            # Определяем конечную дату
            if task['completed_at']:
                end_date = task['completed_at']
                is_completed = True
            else:
                end_date = min(deadline, current_time)
                is_completed = task['status'] == 'completed'

            # Вычисляем метрики
            total_duration = (deadline - start_date).total_seconds() / (24*3600)
            actual_duration = (end_date - start_date).total_seconds() / (24*3600)
            progress = min(actual_duration / total_duration, 1.0) if total_duration > 0 else 0

            # Определяем статус прогресса
            if is_completed:
                progress_status = 'completed'
            elif end_date >= deadline:
                progress_status = 'overdue'
            elif progress > 0.7:
                progress_status = 'at_risk'
            else:
                progress_status = 'on_track'

            gantt_data.append({
                'id': task['id'],
                'task': task['title'][:35] + ('...' if len(task['title']) > 35 else ''),
                'full_title': task['title'],
                'start': start_date,
                'end': end_date,
                'deadline': deadline,
                'status': task['status'],
                'progress_status': progress_status,
                'assignee': task['assignee_name'] or 'Не назначен',
                'progress': progress,
                'total_days': total_duration,
                'actual_days': actual_duration,
                'is_overdue': current_time > deadline and not is_completed,
                'days_left': max(0, (deadline - current_time).days) if current_time < deadline else 0,
                'priority': task.get('priority', 'medium')
            })

        # Сортируем по дедлайну (срочные задачи сверху)
        gantt_data.sort(key=lambda x: (x['is_overdue'], x['deadline']))

        # Создаём премиум диаграмму
        fig = plt.figure(figsize=(20, max(10, len(gantt_data) * 0.8)), facecolor='#ffffff')
        gs = fig.add_gridspec(1, 20, hspace=0, wspace=0)
        ax = fig.add_subplot(gs[0, :18])  # Основная диаграмма
        ax_info = fig.add_subplot(gs[0, 18:])  # Панель информации

        # Премиум стиль
        plt.style.use('default')
        ax.set_facecolor('#ffffff')
        ax_info.set_facecolor('#f8f9fa')

        # Улучшенная цветовая палитра
        status_colors = {
            'new': '#6366f1',          # Indigo
            'in_progress': '#3b82f6',   # Blue
            'completed': '#10b981',     # Emerald
            'overdue': '#ef4444',       # Red
            'cancelled': '#6b7280',     # Gray
            'at_risk': '#f59e0b',       # Amber
            'on_track': '#06b6d4'       # Cyan
        }

        # Градиентные цвета для полос задач
        def get_gradient_color(status, progress):
            base_color = status_colors.get(status, '#6b7280')
            if progress < 0.3:
                return base_color
            elif progress < 0.7:
                return base_color  # Можно добавить градиент
            else:
                return base_color

        y_pos = range(len(gantt_data))

        # Рисуем полосы задач с эффектами
        for i, task_data in enumerate(gantt_data):
            start = task_data['start']
            end = task_data['end']
            deadline = task_data['deadline']
            status = task_data['status']
            progress = task_data['progress']
            progress_status = task_data['progress_status']

            duration = (end - start).total_seconds() / (24*3600)
            color = get_gradient_color(progress_status, progress)

            # Преобразуем datetime в числовое значение
            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            deadline_num = mdates.date2num(deadline)

            # Основная полоса задачи с градиентом
            bar = ax.barh(i, duration, left=start_num, height=0.7,
                          color=color, alpha=0.9, edgecolor='white', linewidth=2)

            # Добавляем тень для 3D эффекта
            ax.barh(i, duration, left=start_num, height=0.7,
                    color='black', alpha=0.1, edgecolor='none', linewidth=0,
                    zorder=-1)

            # Прогресс-индикатор
            if progress > 0:
                progress_width = duration * progress
                ax.barh(i, progress_width, left=start_num, height=0.5,
                        color=color, alpha=1.0, edgecolor='none', linewidth=0)

            # Дедлайн линия с иконкой
            if task_data['is_overdue']:
                # Красная линия для просроченных
                ax.axvline(x=deadline_num, ymin=(i-0.4)/len(gantt_data), ymax=(i+0.4)/len(gantt_data),
                          color='#ef4444', linewidth=3, alpha=0.8, linestyle='--')
                # Иконка предупреждения
                ax.text(deadline_num, i + 0.3, '⚠️', ha='center', va='center',
                       fontsize=12, fontweight='bold')
            else:
                # Обычная дедлайн линия
                ax.axvline(x=deadline_num, ymin=(i-0.4)/len(gantt_data), ymax=(i+0.4)/len(gantt_data),
                          color='#f59e0b', linewidth=2, alpha=0.6, linestyle='-.')

            # Иконка статуса
            status_icons = {
                'completed': '✅',
                'in_progress': '🔄',
                'new': '🆕',
                'overdue': '⏰',
                'cancelled': '❌'
            }
            icon = status_icons.get(status, '📋')
            ax.text(start_num - 0.5, i, icon, ha='center', va='center', fontsize=14)

            # Информация о задаче
            task_text = f"{task_data['task']}\n{task_data['assignee']}"
            ax.text(start_num + duration + 0.5, i, task_text,
                   ha='left', va='center', fontsize=10, fontweight='medium',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='none'))

            # Прогресс бар для незавершенных задач
            if not task_data.get('is_completed', False) and progress < 1:
                # Мини-прогресс бар
                bar_x = start_num + duration + 2
                bar_width = 2
                bar_height = 0.2

                # Фон прогресс бара
                ax.add_patch(plt.Rectangle((bar_x, i - bar_height/2), bar_width, bar_height,
                                         facecolor='#e5e7eb', edgecolor='#d1d5db', linewidth=1))

                # Заполненная часть
                filled_width = bar_width * progress
                if filled_width > 0:
                    ax.add_patch(plt.Rectangle((bar_x, i - bar_height/2), filled_width, bar_height,
                                             facecolor=color, edgecolor='none'))

                # Процент
                ax.text(bar_x + bar_width + 0.2, i, f"{progress:.0%}",
                       ha='left', va='center', fontsize=9, fontweight='bold')

        # Настраиваем основную ось
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"{task['task']}\n{task['assignee']}" for task in gantt_data])
        ax.invert_yaxis()

        # Форматируем ось времени
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m\n%H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))

        # Поворачиваем подписи дат
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')

        # Премиум заголовок
        title_text = "🎯 Диаграмма Ганта - Управление Проектами"
        ax.set_title(title_text, fontsize=24, fontweight='bold', pad=30,
                    color='#1f2937', y=1.02)

        # Подзаголовок с статистикой
        total_tasks = len(gantt_data)
        completed_tasks = len([t for t in gantt_data if t['status'] == 'completed'])
        overdue_tasks = len([t for t in gantt_data if t['is_overdue']])

        completion_rate = completed_tasks / max(total_tasks, 1) * 100
        subtitle = ".1f"
        ax.text(0.5, 0.98, subtitle, ha='center', va='top', fontsize=12,
               color='#6b7280', transform=ax.transAxes, style='italic')

        ax.set_xlabel('Временная шкала', fontsize=14, fontweight='medium', labelpad=20)
        ax.set_ylabel('Задачи', fontsize=14, fontweight='medium', labelpad=20)

        # Улучшенная легенда
        legend_elements = [
            plt.Rectangle((0, 0), 1, 0.6, facecolor=status_colors['new'], label='Новая задача'),
            plt.Rectangle((0, 0), 1, 0.6, facecolor=status_colors['in_progress'], label='В работе'),
            plt.Rectangle((0, 0), 1, 0.6, facecolor=status_colors['completed'], label='Выполнена'),
            plt.Rectangle((0, 0), 1, 0.6, facecolor=status_colors['overdue'], label='Просрочена'),
            plt.Rectangle((0, 0), 1, 0.6, facecolor=status_colors['at_risk'], label='Под угрозой'),
            plt.Line2D([0], [0], color='#f59e0b', linewidth=2, linestyle='-.', label='Дедлайн'),
            plt.Line2D([0], [0], color='#ef4444', linewidth=3, linestyle='--', label='Просрочен')
        ]

        legend = ax.legend(handles=legend_elements, loc='upper left',
                          bbox_to_anchor=(1.02, 1), frameon=True, fancybox=True,
                          shadow=True, fontsize=10, title="Легенда", title_fontsize=12)
        legend.get_frame().set_facecolor('#ffffff')
        legend.get_frame().set_edgecolor('#e5e7eb')

        # Премиум сетка
        ax.grid(True, alpha=0.2, axis='x', linestyle='--', color='#d1d5db')
        ax.grid(False, axis='y')

        # Убираем верхнюю и правую границы
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.5)
        ax.spines['bottom'].set_linewidth(0.5)

        # Панель информации
        ax_info.axis('off')

        # Статистика проекта
        stats_y = 0.95
        ax_info.text(0.1, stats_y, "📊 Статистика проекта", fontsize=12, fontweight='bold',
                    color='#1f2937', va='top')

        stats = [
            ("Всего задач", f"{total_tasks}"),
            ("Выполнено", f"{completed_tasks} ({completed_tasks/max(total_tasks,1)*100:.0f}%)"),
            ("Просрочено", f"{overdue_tasks} ({overdue_tasks/max(total_tasks,1)*100:.0f}%)"),
            ("Активных", f"{total_tasks - completed_tasks - overdue_tasks}"),
        ]

        for i, (label, value) in enumerate(stats):
            ax_info.text(0.1, stats_y - 0.1 - i*0.08, label, fontsize=10, color='#6b7280', va='top')
            ax_info.text(0.8, stats_y - 0.1 - i*0.08, value, fontsize=10, fontweight='bold',
                        color='#1f2937', va='top', ha='right')

        # Текущая дата линия
        current_time_num = mdates.date2num(current_time)
        ax.axvline(x=current_time_num, ymin=0, ymax=1,
                  color='#06b6d4', linewidth=2, alpha=0.8, linestyle='-',
                  label='Текущий момент')
        ax.text(current_time_num, len(gantt_data) + 0.5, 'Сейчас',
               ha='center', va='bottom', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle="round,pad=0.3", facecolor='#06b6d4', edgecolor='none'))

        plt.tight_layout()
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='#ffffff')
        plt.close()

        logger.info(f"Премиум диаграмма Ганта создана: {filepath}")
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
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
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
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
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
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        return filepath

