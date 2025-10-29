import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';

const API_BASE = 'https://functions.poehali.dev/3163a024-78e4-404e-a9ae-b215ace0c6b2';

interface DashboardData {
  stats: {
    total_users: number;
    active_users_24h: number;
    total_orders: number;
    processing_orders: number;
    total_revenue: number;
    credits_spent: number;
  };
  recent_users: Array<{
    user_id: number;
    username: string;
    first_name: string;
    balance: number;
    created_at: string;
    last_activity: string;
    is_blocked: boolean;
  }>;
  recent_orders: Array<{
    order_id: number;
    user_id: number;
    order_type: string;
    status: string;
    cost: number;
    created_at: string;
    username: string;
    first_name: string;
  }>;
  order_stats: Array<{
    order_type: string;
    count: number;
    total_cost: number;
  }>;
  daily_revenue: Array<{
    date: string;
    revenue: number;
    transaction_count: number;
  }>;
}

export default function Index() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}?endpoint=dashboard`)
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load dashboard:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-lg font-medium text-gray-600">Загрузка панели...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Icon name="AlertCircle" className="text-destructive" size={24} />
              Ошибка загрузки
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Не удалось загрузить данные панели администратора.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      pending: 'outline',
      processing: 'secondary',
      completed: 'default',
      failed: 'destructive',
      cancelled: 'outline'
    };
    
    const labels: Record<string, string> = {
      pending: 'Ожидает',
      processing: 'Обработка',
      completed: 'Готово',
      failed: 'Ошибка',
      cancelled: 'Отменён'
    };

    return <Badge variant={variants[status] || 'outline'}>{labels[status] || status}</Badge>;
  };

  const getOrderTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      preview: 'Image',
      'text-to-video': 'Video',
      'image-to-video': 'Film',
      storyboard: 'Clapperboard'
    };
    return icons[type] || 'FileVideo';
  };

  const getOrderTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      preview: 'Превью',
      'text-to-video': 'Текст → Видео',
      'image-to-video': 'Изображение → Видео',
      storyboard: 'Storyboard'
    };
    return labels[type] || type;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      <div className="container mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 via-pink-600 to-orange-500 bg-clip-text text-transparent">
              AI Video Studio
            </h1>
            <p className="text-muted-foreground mt-1">Панель администратора</p>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur rounded-full shadow-sm">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium">Система активна</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium opacity-90">Всего пользователей</CardTitle>
              <Icon name="Users" className="opacity-80" size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.stats.total_users}</div>
              <p className="text-xs opacity-80 mt-1">
                {data.stats.active_users_24h} активных за 24ч
              </p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-pink-500 to-pink-600 text-white border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium opacity-90">Всего заказов</CardTitle>
              <Icon name="ShoppingCart" className="opacity-80" size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.stats.total_orders}</div>
              <p className="text-xs opacity-80 mt-1">
                {data.stats.processing_orders} в обработке
              </p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-orange-500 to-orange-600 text-white border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium opacity-90">Выручка</CardTitle>
              <Icon name="DollarSign" className="opacity-80" size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.stats.total_revenue}₽</div>
              <p className="text-xs opacity-80 mt-1">
                {data.stats.credits_spent} кредитов потрачено
              </p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium opacity-90">Конверсия</CardTitle>
              <Icon name="TrendingUp" className="opacity-80" size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {data.stats.total_users > 0 
                  ? Math.round((data.stats.total_revenue / data.stats.total_users) * 100) / 100
                  : 0}₽
              </div>
              <p className="text-xs opacity-80 mt-1">Средний чек на пользователя</p>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="orders" className="space-y-4">
          <TabsList className="bg-white/80 backdrop-blur">
            <TabsTrigger value="orders" className="gap-2">
              <Icon name="ShoppingBag" size={16} />
              Заказы
            </TabsTrigger>
            <TabsTrigger value="users" className="gap-2">
              <Icon name="Users" size={16} />
              Пользователи
            </TabsTrigger>
            <TabsTrigger value="analytics" className="gap-2">
              <Icon name="BarChart3" size={16} />
              Аналитика
            </TabsTrigger>
          </TabsList>

          <TabsContent value="orders" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Последние заказы</CardTitle>
                <CardDescription>История генераций видео и превью</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {data.recent_orders.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Icon name="Inbox" className="mx-auto mb-2 opacity-50" size={48} />
                      <p>Заказов пока нет</p>
                    </div>
                  ) : (
                    data.recent_orders.map((order) => (
                      <div
                        key={order.order_id}
                        className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-primary/10 rounded-lg">
                            <Icon name={getOrderTypeIcon(order.order_type)} className="text-primary" size={20} />
                          </div>
                          <div>
                            <p className="font-medium">
                              {getOrderTypeLabel(order.order_type)} #{order.order_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {order.first_name} (@{order.username || order.user_id})
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <p className="font-medium">{order.cost} кредитов</p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(order.created_at).toLocaleString('ru')}
                            </p>
                          </div>
                          {getStatusBadge(order.status)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="users" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Пользователи</CardTitle>
                <CardDescription>Зарегистрированные пользователи бота</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {data.recent_users.map((user) => (
                    <div
                      key={user.user_id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white font-bold">
                          {user.first_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium">{user.first_name}</p>
                          <p className="text-sm text-muted-foreground">
                            @{user.username || user.user_id}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-medium">{user.balance} кредитов</p>
                          <p className="text-xs text-muted-foreground">
                            Регистрация: {new Date(user.created_at).toLocaleDateString('ru')}
                          </p>
                        </div>
                        {user.is_blocked && (
                          <Badge variant="destructive">Заблокирован</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Статистика по типам заказов</CardTitle>
                  <CardDescription>Популярность различных видов генераций</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {data.order_stats.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">Нет данных</p>
                  ) : (
                    data.order_stats.map((stat) => {
                      const total = data.order_stats.reduce((sum, s) => sum + s.count, 0);
                      const percentage = total > 0 ? (stat.count / total) * 100 : 0;
                      
                      return (
                        <div key={stat.order_type} className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium flex items-center gap-2">
                              <Icon name={getOrderTypeIcon(stat.order_type)} size={16} />
                              {getOrderTypeLabel(stat.order_type)}
                            </span>
                            <span className="text-muted-foreground">
                              {stat.count} ({Math.round(percentage)}%)
                            </span>
                          </div>
                          <Progress value={percentage} className="h-2" />
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Выручка по дням</CardTitle>
                  <CardDescription>Последние 7 дней</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {data.daily_revenue.length === 0 ? (
                      <p className="text-center text-muted-foreground py-8">Нет транзакций</p>
                    ) : (
                      data.daily_revenue.map((day) => (
                        <div
                          key={day.date}
                          className="flex items-center justify-between p-3 border rounded-lg"
                        >
                          <div>
                            <p className="font-medium">
                              {new Date(day.date).toLocaleDateString('ru', {
                                day: 'numeric',
                                month: 'short'
                              })}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {day.transaction_count} транзакций
                            </p>
                          </div>
                          <p className="text-lg font-bold text-green-600">
                            +{day.revenue}₽
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
