import { ConfigProvider, App as AntApp } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import CardPage from './pages/CardPage'
import Admin from './pages/Admin'
import AdminCard from './pages/AdminCard'
// шрифты бренда (брендбук): Golos Text — интерфейс, Unbounded — название и крупные заголовки
import '@fontsource/golos-text/400.css'
import '@fontsource/golos-text/500.css'
import '@fontsource/golos-text/600.css'
import '@fontsource/golos-text/700.css'
import '@fontsource/unbounded/600.css'
import './styles.css'

function Shell() {
  const admin = useLocation().pathname.startsWith('/admin')
  return (
    <div className="app">
      <header className="top">
        <Link to={admin ? '/admin' : '/'} className="brand">
          <img src="/brand/mark.svg" className="logo" alt="" />
          <span>
            <b className="wordmark">Технотека<i>.</i><span>ИИ</span></b>
            <small>{admin ? 'Модерация карточек' : 'Карточка разработки для Витрины'}</small>
          </span>
        </Link>
        <span className="pilot">пилот</span>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/cards/:id" element={<CardPage />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/admin/cards/:id" element={<AdminCard />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={ruRU} theme={{
      token: {
        colorPrimary: '#1f4e79', borderRadius: 8, fontFamily: "'Golos Text', 'Segoe UI', Roboto, Arial, sans-serif",
        // контраст текста ≥4,5:1 на наших фонах (брендбук): серые и зелёные Ant Design по умолчанию бледнее
        colorTextDescription: '#5f6b7b', colorTextTertiary: '#5f6b7b', colorTextPlaceholder: '#6b7686',
        colorLink: '#1f4e79', colorLinkHover: '#2d6aa3', colorSuccess: '#2b7d0a',
      },
    }}>
      <AntApp>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
