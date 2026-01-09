import simpy
import numpy as np
import random
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


class Library:
    def __init__(self, env, params):
        self.env = env
        self.params = params
        self.librarians = [simpy.Resource(env, capacity = 1) for _ in range(2)]
        
        self.statistic = {
            'ReaderServed': 0,
            'TimeWaiting': [],
            'TimeServed': [],
            'MaxQueueLen': 0,
            'QueueLen': [],
            'LibrarianBusy': [0.0, 0.0],
            'BooksPerReader': []
        }
        self.currentQueueLen = 0

    def ReaderProcess(self, readerId):
        baseTime, variation = self.params['ServeTime'] 

        librarFirstLoad = self.librarians[0].count + len(self.librarians[0].queue)
        librarSecLoad = self.librarians[1].count + len(self.librarians[1].queue)
        if librarFirstLoad < librarSecLoad: librarIndex = 0
        elif librarSecLoad < librarFirstLoad: librarIndex = 1
        else: librarIndex = 0 if self.statistic['LibrarianBusy'][0] < self.statistic['LibrarianBusy'][1] else 1
        
        with self.librarians[librarIndex].request() as req:
            queueStart = self.env.now
            self.currentQueueLen += 1
            self.UpdateQueueStats()
            yield req
            queueWait = self.env.now - queueStart
            self.currentQueueLen -= 1
            self.UpdateQueueStats()
            startServe = self.env.now
            interval = random.uniform(max(1, baseTime - variation), (baseTime + variation))
            yield self.env.timeout(interval)
            getBooks = random.randint(1, 5)
            self.statistic['TimeWaiting'].append(queueWait)
            self.statistic['TimeServed'].append(self.env.now - startServe)
            self.statistic['ReaderServed'] += 1
            self.statistic['LibrarianBusy'][librarIndex] += self.env.now - startServe
            self.statistic['BooksPerReader'].append(getBooks)

    def UpdateQueueStats(self):
        self.statistic['MaxQueueLen'] = max(self.statistic['MaxQueueLen'], self.currentQueueLen)
        self.statistic['QueueLen'].append((self.env.now, self.currentQueueLen))
    
def ReaderGenerator(env, library):
    readerId = 1
    if library.params['ArrivalLaw'] == "Безперервний рівномірний":
        baseTime, variation = library.params['ArrivalTime'] 
        while True:
            interval = random.uniform(max(1, baseTime - variation), (baseTime + variation))
            yield env.timeout(interval)
            env.process(library.ReaderProcess(readerId))
            readerId += 1
    elif library.params['ArrivalLaw'] == "Експоненційний":
        while True:
            interval = random.expovariate(1.0 / library.params['ArrivalTime'][0])
            yield env.timeout(interval)
            env.process(library.ReaderProcess(readerId))
            readerId += 1
    elif library.params['ArrivalLaw'] == "Нормальний":
        while True:
            baseTime, variation = library.params['ArrivalTime'] 
            interval = max(0.1, random.gauss(baseTime, variation))
            yield env.timeout(interval)
            env.process(library.ReaderProcess(readerId))
            readerId += 1
    elif library.params['ArrivalLaw'] == "Пуассона":
        while True:
            yield env.timeout(3600)
            readerN = np.random.poisson(library.params['ArrivalTime'][0])
            for _ in range(readerN):
                env.process(library.ReaderProcess(readerId))
                readerId += 1

def CreateHistogram(data, title, xLabel, yLabel, color = '#1f77b4'):
    if not data:
        return None
    
    fig = px.histogram(
        x = data,
        nbins = 20,
        title = title,
        labels = {'x': xLabel, 'y': yLabel},
        opacity = 0.7,
        color_discrete_sequence = [color]
    )

    fig.update_layout(
        bargap = 0.1,
        showlegend = False,
        xaxis_title = xLabel,
        yaxis_title = yLabel
    )

    meanVal = np.mean(data)
    fig.add_vline(x = meanVal, line_dash = 'dash', line_color = 'cyan', annotation_text = f"Середнє: {meanVal:.2f}")

    return fig

def CreateTimeSeriesChart(timeData, valueData, title, yLabel):
    if not timeData:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x = timeData,
        y = valueData,
        mode = 'lines',
        name = yLabel,
        line = dict(width = 2, shape='hv')
    ))

    fig.update_layout(
        title = title,
        xaxis_title = 'Час (секунди)',
        yaxis_title = yLabel,
        showlegend = True
    )

    return fig

def RunSim(params):
    env = simpy.Environment()
    library = Library(env, params)

    env.process(ReaderGenerator(env, library))
    env.run(until = params['SimTime'])

    return library.statistic

def Main():
    st.set_page_config(page_title = "Моделювання бібліотеки", layout = 'wide', page_icon = "🏛️")
    st.title("📚 Моделювання роботи бібліотеки", text_alignment = 'center')
    st.markdown("---")

    st.header("⚙️ Параметри моделювання")
    simulationHours = st.slider("Час моделювання (годин)", 1, 24, 5)
    options = ["Безперервний рівномірний", "Експоненційний", "Нормальний", "Пуассона"]
    selected = st.selectbox("Оберіть закон розподілу прибуття читачів", options)
    col1, col2 = st.columns(2)
    if selected == "Безперервний рівномірний":
        with col1: arrivalTime = st.slider("Час прибуття читачів кожні (хвилини)", 1, 60, 8)
        with col2: arrivalTimePlusMinus = st.slider("± (хвилин)", 1, 60, 2, key = "arrival")
    elif selected == "Експоненційний":
        arrivalTime = st.slider("Середнє значення інтервалу приходу (хвилини)", 1, 60, 2)
    elif selected == "Нормальний":
        with col1: arrivalTime = st.slider("Час прибуття читачів кожні (хвилини)", 1, 60, 8)
        with col2: arrivalTimePlusMinus = st.slider("± (хвилин)", 1, 60, 2, key = "arrival")
    elif selected == "Пуассона":
        arrivalTime = st.slider("Середня кількість клієнтів на годину", 1, 100, 8)
    col1, col2 = st.columns(2)
    with col1: serveTime = st.slider("Час обслуговування на видачі книг (хвилин)", 1, 60, 3)
    with col2: serveTimePlusMinus = st.slider("± (хвилин)", 1, 60, 2, key = "serve")

    params = {
        'SimTime': simulationHours * 3600,
        'ServeTime': (serveTime * 60, serveTimePlusMinus * 60),
        'ArrivalLaw': selected
    }
    if selected == "Безперервний рівномірний": params['ArrivalTime'] = (arrivalTime * 60, arrivalTimePlusMinus * 60)
    elif selected == "Експоненційний": params['ArrivalTime'] = (arrivalTime * 60, 0)
    elif selected == "Нормальний": params['ArrivalTime'] = (arrivalTime * 60, arrivalTimePlusMinus * 60)
    elif selected == "Пуассона": params['ArrivalTime'] = (arrivalTime, 0)

    if st.button("🚀 Запустити моделювання", type = 'primary', use_container_width = True):
        RunAndDisplaySim(params)
    else: st.info("👈 Оберіть параметри моделювання та натисніть кнопку 'Запустити моделювання'")

def RunAndDisplaySim(params):
    progresBar = st.progress(0)
    statusText = st.empty()

    for i in range(100):
        progresBar.progress(i + 1)
        statusText.text(f"⏳ Виконується моделювання... {i + 1}%")

    with st.spinner("🔄 Виконується моделювання..."):
        results = RunSim(params)

    st.success("✅ Моделювання завершено!")
    st.markdown("---")
    st.header("📍 Встановленні параметри моделювання")
    st.metric("Закон розподілу прибуття читачів", params['ArrivalLaw'])
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Час моделювання (годин)", params['SimTime'] / 3600)
    with col2:
        if params["ArrivalLaw"] in ("Безперервний рівномірний", "Нормальний"):
            st.metric("Час прибуття читачів кожні (хвилини)", f"{params['ArrivalTime'][0] / 60}±{params['ArrivalTime'][1] / 60}")
        elif params["ArrivalLaw"] == "Експоненційний":
            st.metric("Середнє значення інтервалу приходу (хвилини)", f"{params['ArrivalTime'][0] / 60}")
        elif params["ArrivalLaw"] == "Пуассона":
            st.metric("Середня кількість клієнтів на годину", f"{params['ArrivalTime'][0]}")
    with col3: st.metric("Час обслуговування на видачі книг (хвилин)", f"{params['ServeTime'][0] / 60}±{params['ServeTime'][1] / 60}")
    st.markdown("---")

    st.header("📈 Основні результати")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Обслужено читачів", results['ReaderServed'])
    with col2: st.metric("Середній час очікування в черзі (сек)", f"{np.mean(results['TimeWaiting']):.2f}")
    with col3: st.metric("Середній час обслуговування (сек)", f"{np.mean(results['TimeServed']):.2f}")
    with col4: st.metric("Максимальна кількість читачів в залі очікування", results['MaxQueueLen'])
    libFirstKoef = min(1.0, results['LibrarianBusy'][0] / params['SimTime'])
    libSecondKoef = min(1.0, results['LibrarianBusy'][1] / params['SimTime'])
    libKoef = min(1.0, sum(results['LibrarianBusy']) / (2 * params['SimTime']))
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Коефіцієнт зайнятості першого бібліотекаря {libFirstKoef * 100:.1f}%")
        st.progress(libFirstKoef)
    with col2:
        st.write(f"Коефіцієнт зайнятості другого бібліотекаря {libSecondKoef * 100:.1f}%")
        st.progress(libSecondKoef)
    st.markdown(f"<p style='text-align: center;'>Коефіцієнт зайнятості бібліотекарів {libKoef * 100:.1f}%</p>", unsafe_allow_html = True)
    st.progress(libKoef)

    st.header("⏰ Динаміка системи в часі")
    if results['QueueLen'] and len(results['QueueLen']) > 10:
        sampleSize = min(1000, len(results['QueueLen']))
        step = len(results['QueueLen']) // sampleSize
        times = [t for i, (t, _) in enumerate(results['QueueLen']) if i % step == 0]
        queues = [q for i, (_, q) in enumerate(results['QueueLen']) if i % step == 0] 
        
        figQueue = CreateTimeSeriesChart(
            times, queues,
            "Динаміка довжини черги",
            "Довжина черги"
        )
        if figQueue: st.plotly_chart(figQueue, use_container_width = True)

    st.header("📊 Гістограми розподілів")
    col1, col2 = st.columns(2)
    if results['TimeWaiting']:
        with col1:
            figWait = CreateHistogram(
                results['TimeWaiting'],
                "Розподіл часу очікування в черзі",
                "Час очікування (секунди)",
                "Кількість читачів",
                "#6E3FC7"
            )
            if figWait: st.plotly_chart(figWait, use_container_width = True)
    if results['TimeServed']:
        with col2:
            figServe = CreateHistogram(
                results['TimeServed'],
                "Розподіл часу обслуговування",
                "Час обслуговування (секунди)",
                "Кількість читачів",
                "#74EE02"
            )
            if figServe: st.plotly_chart(figServe, use_container_width = True)

    if results['BooksPerReader']:
        figBooks = CreateHistogram(
            results['BooksPerReader'],
            "Розподіл кількості виданих книг",
            "Кількість книг (шт)",
            "Кількість випадків",
            "#F5AA1E"
        )
        figBooks.update_traces(nbinsx = 5) 
        if figBooks: st.plotly_chart(figBooks, use_container_width = True)

    st.header("🔍 Детальна статистика")
    st.subheader("Загальні показники")
    metricData = {
        'Показник': [
            'Загальна кількість обслужених читачів (люд)',
            'Максимальна черга (люд)',
            'Середній час очікування (сек)',
            'Середній час обслуговування (сек)',
            'Загальна кількість виданих книжок (шт)',
            'Середня кількість виданих книжок (шт)',
            'Загальний час роботи бібліотекарів (сек)',
            'Коефіцієнт зайнятості бібліотекарів (%)',
            'Загальний час роботи 1 бібліотекаря (сек)',
            'Коефіцієнт зайнятості 1 бібліотекаря (%)',
            'Загальний час роботи 2 бібліотекаря (сек)',
            'Коефіцієнт зайнятості 2 бібліотекаря (%)'
        ],
        'Значення': [
            results['ReaderServed'],
            results['MaxQueueLen'],
            round(np.mean(results['TimeWaiting']), 2) if results['TimeWaiting'] else 0,
            round(np.mean(results['TimeServed']), 2) if results['TimeServed'] else 0,
            np.sum(results['BooksPerReader']) if results['BooksPerReader'] else 0,
            round(np.mean(results['BooksPerReader']), 1) if results['BooksPerReader'] else 0,
            round(np.sum(results['LibrarianBusy']), 2),
            round(libKoef * 100, 2),
            round(results['LibrarianBusy'][0], 2),
            round(libFirstKoef * 100, 2),
            round(results['LibrarianBusy'][1], 2),
            round(libSecondKoef * 100, 2)
        ]
    }

    metricDf = pd.DataFrame(metricData)
    st.dataframe(metricDf, use_container_width = True, hide_index = True)
        
if __name__ == '__main__': Main()
