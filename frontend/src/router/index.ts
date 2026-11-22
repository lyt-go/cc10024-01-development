import { createRouter, createWebHistory } from 'vue-router'

import ExtractRehearsalView from '@/views/ExtractRehearsalView.vue'
import Overview from '@/views/Overview.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    // 抽取锚点绑定预演：数据抽取模块的专用视图，放在通配模块路由之前
    { path: '/data_extract/rehearsal', name: 'extract-rehearsal', component: ExtractRehearsalView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
