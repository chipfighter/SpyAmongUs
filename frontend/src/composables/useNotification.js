/**
 * 房间通知 composable
 *
 * 从 RoomView.vue 提取的通知显示逻辑。
 * 创建临时 DOM 通知元素并自动移除。
 */

/**
 * @returns {{ showNotification: (type: string, message: string) => void }}
 */
export function useNotification() {
    /**
     * 在页面右上角显示一条临时通知
     * @param {'info'|'success'|'warning'|'error'} type
     * @param {string} message
     */
    function showNotification(type, message) {
        // 跳过投票成功和玩家淘汰的提示消息（避免重复通知）
        if (message.startsWith('你已成功投票给') || message.includes('被淘汰，身份是')) {
            console.log(`[Notification] 跳过: ${message}`)
            return
        }

        console.log(`[Notification] ${type}: ${message}`)

        const notification = document.createElement('div')
        notification.className = `room-notification ${type}`
        notification.innerHTML = `
      <div class="notification-content">
        <span class="notification-icon">${type === 'success' ? '✅' : type === 'warning' ? '⚠️' : type === 'error' ? '❌' : 'ℹ️'
            }</span>
        <span class="notification-message">${message}</span>
      </div>
    `

        document.body.appendChild(notification)

        // 进入动画
        setTimeout(() => notification.classList.add('show'), 10)

        // 5 秒后移除
        setTimeout(() => {
            notification.classList.remove('show')
            notification.classList.add('hide')
            setTimeout(() => {
                if (notification.parentNode) notification.parentNode.removeChild(notification)
            }, 300)
        }, 5000)
    }

    return { showNotification }
}
