import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 如果需要持久化，引入插件: import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import App from './App.vue'
import router from './router'

const pinia = createPinia()
// 如果需要持久化，使用插件: pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(pinia) // 确保先 use(pinia)
app.use(router)
app.mount('#app')