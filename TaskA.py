import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from datetime import datetime
import numpy as np
import io
import simpy
import random

DEFAULTPARAMS = {
    'simTime': 8 * 3600,
    'meanInterval': 75,
    'payTimePerItem': 3
}

COUNTERSDATA = {
    1: {'probability': 0.75, 'time': (120, 60), 'purchases': (3, 1)},
    2: {'probability': 0.55, 'time': (150, 30), 'purchases': (4, 1)},
    3: {'probability': 0.82, 'time': (120, 45), 'purchases': (5, 1)}
}

class Supermarket:
    def __init__(self, env, params):
        self.env = env
        self.params = params
        self.counters = [simpy.Resource(env, capacity = 1) for _ in range(3)]
        self.cashier = simpy.Resource(env, capacity = 1)

        self.stats = {
            'customersServed': 0,
            'maxQueueLength': 0,
            'maxBasketsInUse': 0,
            'cashierBusyTime': 0,
            'queueLengths': [],
            'basketsInUse': 0,
            'basketsHistory': [],
            'serviceTimes': [],
            'waitTimes': [],
            'purchaseCounts': [],
            'customerData': []
        }

        self.currentQueueLength = 0
        self.cashierBusyStart = None
    
    def CustomerProcess(self, customerId):
        arrivalTime = self.env

        self.stats['basketsInUse'] += 1
        self.UpdateBasketStats()

        totalPurchases = yield from self.VisitCounters(customerId)
        extraPurchases = random.randint(1, 3)
        totalPurchases += extraPurchases

        queueStartTime = self.env.now
        yield from self.CashierProcess(customerId, totalPurchases)
        waitTime = self.env.now - queueStartTime

        self.stats['basketsInUse'] -= 1
        self.UpdateBasketStats()

        self.stats['customersServed'] += 1
        self.stats['purchaseCounts'].append(totalPurchases)
        self.stats['waitTimes'].append(waitTime)

        customerData = {
            'id': customerId,
            'arrivalTime': arrivalTime,
            'totalPurchases': totalPurchases,
            'waitTime': waitTime,
            'serviceTime': totalPurchases * self.params['payTimePerItem'],
            'exitTime': self.env.now
        }
        self.stats['customerData'].append(customerData)

    def VisitCounters(self, customerId):
        totalPurchases = 0

        for counterId, counterData in COUNTERSDATA.items():
            if random.random() < counterData['probability']:
                with self.counters[counterId - 1].request() as req:
                    yield req

                    baseTime, variation = counterData['time']
                    selectionTime = random.uniform(
                        max(0, baseTime - variation),
                        baseTime + variation
                    )
                    yield self.env.timeout(selectionTime)

                    basePurchases, purchaseVariation = counterData['purchases']
                    purchases = random.randint(
                        max(1, basePurchases - purchaseVariation),
                        basePurchases + purchaseVariation
                    )
                    totalPurchases += purchases
        
        return totalPurchases
    
    def CashierProcess(self, customerId, totalPurchases):
        self.currentQueueLength += 1
        self.UpdateQueueStats()

        if self.cashierBusyStart is None:
            self.cashierBusyStart = self.env.now
        
        with self.cashier.request() as req:
            yield req

            self.currentQueueLength -= 1
            self.UpdateQueueStats()

            serviceTime = totalPurchases * self.params['payTimePerItem']
            self.stats['serviceTimes'].append(serviceTime)

            yield self.env.timeout(serviceTime)

            if self.cashierBusyStart is not None:
                self.stats['cashierBusyTime'] += (self.env.now - self.cashierBusyStart)
                self.cashierBusyStart = None
    
    def UpdateQueueStats(self):
        self.stats['maxQueueLength'] = max(self.stats['maxQueueLength'], self.currentQueueLength)
        self.stats['queueLengths'].append((self.env.now, self.currentQueueLength))

    def UpdateBasketStats(self):
        self.stats['maxBasketsInUse'] = max(self.stats['maxBasketsInUse'], self.stats['basketsInUse'])
        self.stats['basketsHistory'].append((self.env.now, self.stats['basketsInUse']))

def CustomerGenerator(env, supermarket):
    customerId = 1
    while True:
        interval = random.expovariate(1.0 / supermarket.params['meanInterval'])
        yield env.timeout(interval)
        env.process(supermarket.CustomerProcess(customerId))
        customerId += 1

def RunSim(params):
    env = simpy.Environment()
    supermarket = Supermarket(env, params)

    env.process(CustomerGenerator(env, supermarket))
    env.run(until = params['simTime'])

    if supermarket.cashierBusyStart is not None:
        supermarket.stats['cashierBusyTime'] += (params['simTime'] - supermarket.cashierBusyStart)

    return supermarket.stats

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
    fig.add_vline(x = meanVal, line_dash = 'dash', line_color = 'red', annotation_text = f"Середнє: {meanVal:.2f}")

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
        line = dict(width = 2)
    ))

    fig.update_layout(
        title = title,
        xaxis_title = 'Час (секунди)',
        yaxis_title = yLabel,
        showlegend = True
    )

    return fig

def main():
    st.set_page_config(page_title = "Моделювання магазину", layout = 'wide')
    st.title("🛒 Моделювання роботи продовольчого магазину")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Параметри моделювання")
        simulationHours = st.slider("Час моделювання (годин)", 1, 24, 8)
        meanInterarrival = st.slider("Середній інтервал прибуття (сек)", 30, 120, 75)
        cashierSpeed = st.slider("Час на одну покупку (сек)", 1, 10, 3)

        params = {
            'simTime': simulationHours * 3600,
            'meanInterval': meanInterarrival,
            'payTimePerItem': cashierSpeed
        }

        st.header("📊 Параметри прилавків")
        for counterId, counterData in COUNTERSDATA.items():
            st.subheader(f"Прилавок {counterId}")
            st.write(f"Ймовірність відвідування: {counterData['probability']}")
            st.write(f"Час вибору: {counterData['time'][0]}±{counterData['time'][1]} сек")
            st.write(f"Покупки: {counterData['purchases'][0]}±{counterData['purchases'][1]} шт")
        if st.button("🚀 Запустити моделювання", type = 'primary', use_container_width = True):
            RunAndDisplaySim(params)
        else: st.info("👈 Оберіть параметри моделювання та натисніть кнопку 'Запустити моделювання'")

def RunAndDisplaySim(params):
    progressBar = st.progress(0)
    statusText = st.empty()

    for i in range(100):
        progressBar.progress(i + 1)
        statusText.text(f"⏳ Виконується моделювання... {i + 1}%")

    with st.spinner("🔄 Виконується моделювання..."):
        results = RunSim(params)

    st.success("✅ Моделювання завершено!")
    st.header("📈 Основні результати")

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Обслужено покупці", results['customersServed'])
    with col2: st.metric("Макс. черга біля каси", results["maxQueueLength"])
    with col3: st.metric("Макс. корзинок одночасно", results['maxBasketsInUse'])
    with col4: 
        cashierUtilization = (results['cashierBusyTime'] / params["simTime"]) * 100
        st.metric("Завантаження касира", f"{cashierUtilization:.1f}%")

    st.header("📊 Гістограми розподілів")
    if results['waitTimes']:
        col1, col2 = st.columns(2)

        with col1:
            figWait = CreateHistogram(
                results['waitTimes'],
                "Розподіл часу очікування в черзі",
                "Час очікування (секунди)",
                "Кількість покупців",
                '#FF6B6B'
            )
            if figWait: st.plotly_chart(figWait, use_container_width = True)

        with col2:
            figPurchases = CreateHistogram(
                results['purchaseCounts'],
                "Розподіл кількості покупок на покупця",
                "Кількість покупок",
                "Кількість покупців",
                '#4ECDC4'
            )
            if figPurchases: st.plotly_chart(figPurchases, use_container_width = True)

    if results['serviceTimes']:
        col1, col2 = st.columns(2)

        with col1:
            figService = CreateHistogram(
                results['serviceTimes'],
                "Розподіл часу обслуговування на касі",
                "Час обслуговування (секунди)",
                "Кількість покупців",
                '#45B7D1'
            )
            if figService: st.plotly_chart(figService, use_container_width = True)

    st.header("⏰ Динаміка системи в часі")

    if results['queueLengths'] and len(results['queueLengths']) > 10:
        sampleSize = min(1000, len(results['queueLengths']))
        step = len(results['queueLengths']) // sampleSize
        times = [t for i, (t, _) in enumerate(results['queueLengths']) if i % step == 0]
        queues = [q for i, (_, q) in enumerate(results['queueLengths']) if i % step == 0]

        figQueue = CreateTimeSeriesChart(
            times, queues,
            "Динаміка довжини черги біля каси",
            "Довжина черги"
        )
        if figQueue: st.plotly_chart(figQueue, use_container_width = True)

    if results['basketsHistory'] and len(results['basketsHistory']) > 10:
        sampleSize = min(1000, len(results['basketsHistory']))
        step = len(results['basketsHistory']) // sampleSize

        times = [t for i, (t, _) in enumerate(results["basketsHistory"]) if i % step == 0]
        baskets = [b for i, (_, b) in enumerate(results['basketsHistory']) if i % step == 0]

        figBaskets = CreateTimeSeriesChart(
            times, baskets,
            "Динаміка використання корзинок",
            "Кількість корзинок"
        )
        if figBaskets: st.plotly_chart(figBaskets, use_container_width = True)

    st.header("🔍 Детальна статистика")
    if results['customerData']:
        df = pd.DataFrame(results['customerData'])

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Статистика покупців")
            st.dataframe(df.describe(), use_container_width = True)

        with col2:
            st.subheader("Загальні показники")

            metricsData = {
                'Показник': [
                    'Загальна кількість покупців',
                    'Середній час очікування (сек)',
                    'Середня кількість покупок (шт)',
                    'Загальний час роботи касира (сек)',
                    'Максимальна черга'
                ],
                'Значення': [
                    results['customersServed'],
                    np.mean(results['waitTimes']) if results['waitTimes'] else 0,
                    np.mean(results['purchaseCounts']) if results['purchaseCounts'] else 0,
                    results['cashierBusyTime'],
                    results['maxQueueLength']
                ]
            }

            metricDf = pd.DataFrame(metricsData)
            st.dataframe(metricDf, use_container_width = True, hide_index = True)

    st.header("💾 Експорт результатів")

    if results['customerData']:
        df = pd.DataFrame(results['customerData'])
        csv = df.to_csv(index = False)
        st.download_button(
            label = "📥 Завантажити дані у CSV",
            data = csv,
            file_name = f"supermarket_simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime = "text/csv",
            use_container_width = True
        )

if __name__ == '__main__': main()