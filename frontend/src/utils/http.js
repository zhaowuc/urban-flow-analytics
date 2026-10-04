import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 120000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('urban-flow-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail || error.message || '请求失败'
    if (error.response?.status === 401 && !location.pathname.includes('/login')) {
      localStorage.removeItem('urban-flow-token')
      localStorage.removeItem('urban-flow-user')
      location.href = '/login'
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '请求处理失败')
    }
    return Promise.reject(error)
  },
)

export default http
