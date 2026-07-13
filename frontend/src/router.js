import Vue from 'vue'
import VueRouter from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import ReviewPage from './views/ReviewPage.vue'
import PendingReviews from './views/PendingReviews.vue'
import History from './views/History.vue'
import LegalKBPage from './views/LegalKBPage.vue'
import AgentMonitor from './views/AgentMonitor.vue'

Vue.use(VueRouter)

export default new VueRouter({
  routes: [
    { path: '/', name: 'Dashboard', component: Dashboard, meta: { title: '工作台' } },
    { path: '/review', name: 'Review', component: ReviewPage, meta: { title: '智能审查' } },
    { path: '/pending', name: 'Pending', component: PendingReviews, meta: { title: '待审批' } },
    { path: '/history', name: 'History', component: History, meta: { title: '审查记录' } },
    { path: '/legal-kb', name: 'LegalKB', component: LegalKBPage, meta: { title: '法律知识库' } },
    { path: '/agents', name: 'Agents', component: AgentMonitor, meta: { title: 'Agent 监控' } },
  ]
})
