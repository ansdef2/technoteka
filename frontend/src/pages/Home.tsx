// Вход по ссылке-приглашению (?t=…) и список карточек организации.
import { Alert, App, Button, Card, List, Result, Space, Spin, Tag, Typography } from 'antd'
import { ArrowRightOutlined, FormOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError, MODE, STATUS, type CardShort, type Mode, type Session } from '../api'

const { Title, Paragraph, Text } = Typography

export default function Home() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const { message } = App.useApp()
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const t = params.get('t')
    const p = t ? api.login(t) : api.session()
    p.then((s) => {
      setSession(s)
      if (t) nav('/', { replace: true }) // токен не оставляем в адресной строке
    }).catch((e: ApiError) => setError(e.message))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return <Result status="info" title="Откройте ссылку-приглашение"
      subTitle={<>Доступ к пилоту — по персональной ссылке из письма. <br /><Text type="secondary">{error}</Text></>} />
  }
  if (!session) return <div className="center"><Spin size="large" /></div>

  const start = async (mode?: Mode) => {
    setBusy(true)
    try {
      const card = await api.createCard(mode)
      nav(`/cards/${card.id}`)
    } catch (e) {
      message.error((e as Error).message)
      setBusy(false)
    }
  }

  const two = session.plan.length > 1
  return (
    <div className="narrow">
      <Title level={2} style={{ marginBottom: 4 }}>Здравствуйте!</Title>
      <Paragraph type="secondary" style={{ fontSize: 16 }}>{session.org_label}</Paragraph>
      <Paragraph style={{ fontSize: 16 }}>
        Здесь вы заполняете карточку своей разработки для Витрины разработок. Загрузите материалы
        (презентацию, описание, техпаспорт) — система сама заполнит поля карточки, а вы проверите и поправите.
      </Paragraph>
      {two && (
        <Alert type="info" showIcon style={{ marginBottom: 20 }}
          message="В пилоте две карточки — по двум разным разработкам"
          description="Одну вы заполните с автозаполнением, другую — вручную, в указанном порядке. Так мы честно измерим, сколько времени экономит ИИ. Время считается от открытия карточки до отправки — делать перерывы можно." />
      )}
      <List
        dataSource={[
          ...session.plan.map((mode, i) => ({ mode, i, card: session.cards[i] as CardShort | undefined })),
          ...session.cards.slice(session.plan.length).map((card, j) => ({ mode: card.mode, i: session.plan.length + j, card })),
        ]}
        renderItem={({ mode, i, card }) => {
          const next = i === session.cards.length
          return (
            <Card className="home-card" size="small" hoverable={!!card} onClick={() => card && nav(`/cards/${card.id}`)}>
              <div className="home-row">
                <div className="home-icon">{mode === 'ai' ? <RobotOutlined /> : <FormOutlined />}</div>
                <div className="home-text">
                  <Text strong>Карточка {i + 1}: {MODE[mode].toLowerCase()}</Text>
                  <div><Text type="secondary">{card?.title || (card ? 'Без названия' : mode === 'ai'
                    ? 'Загрузите материалы — поля заполнятся автоматически' : 'Заполните поля вручную по своим материалам')}</Text></div>
                </div>
                {card && (
                  <div className="home-meta">
                    <Tag color={STATUS[card.status].color}>{STATUS[card.status].label}</Tag>
                    <ArrowRightOutlined />
                  </div>
                )}
                {!card && next && <Button type="primary" loading={busy} onClick={() => start()}>Начать</Button>}
                {!card && !next && <Text type="secondary">после карточки {i}</Text>}
              </div>
            </Card>
          )
        }}
      />
      {/* карточки по плану пилота — сначала и по порядку (замер времени), потом свои — сколько нужно */}
      {session.cards.length >= session.plan.length && (
        <Card className="home-card home-add" size="small">
          <div className="home-row">
            <div className="home-icon"><PlusOutlined /></div>
            <div className="home-text">
              <Text strong>Ещё одна разработка</Text>
              <div><Text type="secondary">Отдельная карточка для каждой разработки организации</Text></div>
            </div>
            <Space wrap>
              <Button type="primary" icon={<RobotOutlined />} loading={busy} onClick={() => start('ai')}>С автозаполнением</Button>
              <Button icon={<FormOutlined />} loading={busy} onClick={() => start('manual')}>Вручную</Button>
            </Space>
          </div>
        </Card>
      )}
    </div>
  )
}
