import { ConfigProvider, App as AntApp } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import CardPage from './pages/CardPage'
import Admin from './pages/Admin'
import AdminCard from './pages/AdminCard'
import './styles.css'

function Shell() {
  const admin = useLocation().pathname.startsWith('/admin')
  return (
    <div className="app">
      <header className="top">
        <Link to={admin ? '/admin' : '/'} className="brand">
          <span className="logo">Т</span>
          <span>
            <b>Технотека.ИИ</b>
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
      token: { colorPrimary: '#1f4e79', borderRadius: 8, fontFamily: "'Inter', 'Segoe UI', Roboto, Arial, sans-serif" },
    }}>
      <AntApp>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
