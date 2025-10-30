import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';

const API_BASE = 'https://functions.poehali.dev/3163a024-78e4-404e-a9ae-b215ace0c6b2';
const ADMIN_KEY = import.meta.env.VITE_ADMIN_SECRET_KEY || '';

interface DashboardData {
  stats: {
    total_users: number;
    active_users_24h: number;
    total_orders: number;
    processing_orders: number;
    total_revenue: number;
    credits_spent: number;
    total_errors?: number;
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
  model_stats: Array<{
    order_type: string;
    total_count: number;
    completed_count: number;
    failed_count: number;
    total_revenue: number;
  }>;
}

export default function Index() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [balanceDialogOpen, setBalanceDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<number | null>(null);
  const [balanceAmount, setBalanceAmount] = useState('');
  const [balanceReason, setBalanceReason] = useState('');
  const [updating, setUpdating] = useState(false);
  const [resettingStats, setResettingStats] = useState(false);

  const loadDashboard = () => {
    setLoading(true);
    fetch(`${API_BASE}?endpoint=dashboard`, {
      headers: { 'X-Admin-Key': ADMIN_KEY }
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        if (data && data.stats) {
          setData(data);
        } else {
          console.error('Invalid data format:', data);
          setData(null);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load dashboard:', err);
        setData(null);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const handleUpdateBalance = async () => {
    if (!selectedUser || !balanceAmount) return;

    setUpdating(true);
    try {
      const response = await fetch(API_BASE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': ADMIN_KEY
        },
        body: JSON.stringify({
          action: 'update_balance',
          user_id: selectedUser,
          amount: parseInt(balanceAmount),
          admin_username: 'admin',
          reason: balanceReason || 'Корректировка баланса'
        })
      });

      const result = await response.json();
      
      if (result.success) {
        setBalanceDialogOpen(false);
        setBalanceAmount('');
        setBalanceReason('');
        setSelectedUser(null);
        loadDashboard();
      } else {
        alert('Ошибка: ' + (result.error || 'Не удалось обновить баланс'));
      }
    } catch (err) {
      console.error('Failed to update balance:', err);
      alert('Ошибка при обновлении баланса');
    } finally {
      setUpdating(false);
    }
  };

  const handleResetStats = async () => {
    if (!confirm('Вы уверены, что хотите обнулить статистику? Это действие нельзя отменить.')) {
      return;
    }

    setResettingStats(true);
    try {
      const response = await fetch(API_BASE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': ADMIN_KEY
        },
        body: JSON.stringify({
          action: 'reset_stats',
          admin_username: 'admin'
        })
      });

      const result = await response.json();

      if (result.success) {
        alert('✅ Статистика успешно сброшена!');
        loadDashboard();
      } else {
        alert('❌ Ошибка: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Failed to reset stats:', error);
      alert('❌ Не удалось сбросить статистику');
    } finally {
      setResettingStats(false);
    }
  };

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

  if (!data || !data.stats) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Icon name="AlertCircle" className="text-destructive" size={24} />
              Ошибка загрузки
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">Не удалось загрузить данные панели администратора.</p>
            {!ADMIN_KEY && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-sm text-yellow-800">
                  ⚠️ Не установлен секретный ключ ADMIN_SECRET_KEY
                </p>
              </div>
            )}
            <Button onClick={loadDashboard} className="w-full">
              <Icon name="RefreshCw" size={16} className="mr-2" />
              Попробовать снова
            </Button>
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

          <Card className="bg-gradient-to-br from-red-500 to-red-600 text-white border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium opacity-90">Ошибки</CardTitle>
              <Icon name="AlertTriangle" className="opacity-80" size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.stats.total_errors || 0}</div>
              <p className="text-xs opacity-80 mt-1">
                Всего зафиксировано
              </p>
            </CardContent>
          </Card>
        </div>

        <Card className="border-2 border-purple-200 shadow-lg">
          <CardHeader className="bg-gradient-to-r from-purple-50 to-pink-50">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Icon name="BarChart3" size={24} className="text-purple-600" />
                  Статистика проекта
                </CardTitle>
                <CardDescription>Текущие агрегаты из базы данных</CardDescription>
              </div>
              <Button 
                onClick={handleResetStats}
                disabled={resettingStats}
                variant="destructive"
                size="sm"
              >
                <Icon name="RotateCcw" size={16} className="mr-2" />
                {resettingStats ? 'Сброс...' : 'Обнулить статистику'}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon name="Users" size={18} />
                  <span className="text-sm font-medium">Пользователи</span>
                </div>
                <div className="text-2xl font-bold">{data.stats.total_users}</div>
                <p className="text-xs text-muted-foreground">{data.stats.active_users_24h} активных за 24ч</p>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon name="ShoppingCart" size={18} />
                  <span className="text-sm font-medium">Заказы</span>
                </div>
                <div className="text-2xl font-bold">{data.stats.total_orders}</div>
                <p className="text-xs text-muted-foreground">{data.stats.processing_orders} в обработке</p>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon name="DollarSign" size={18} />
                  <span className="text-sm font-medium">Выручка</span>
                </div>
                <div className="text-2xl font-bold">{data.stats.total_revenue}₽</div>
                <p className="text-xs text-muted-foreground">{data.stats.credits_spent} кредитов потрачено</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="users" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3 lg:w-auto">
            <TabsTrigger value="users">
              <Icon name="Users" size={16} className="mr-2" />
              Пользователи
            </TabsTrigger>
            <TabsTrigger value="orders">
              <Icon name="ShoppingCart" size={16} className="mr-2" />
              Заказы
            </TabsTrigger>
            <TabsTrigger value="analytics">
              <Icon name="BarChart3" size={16} className="mr-2" />
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
                        <Dialog open={balanceDialogOpen && selectedUser === user.user_id} onOpenChange={(open) => {
                          setBalanceDialogOpen(open);
                          if (!open) {
                            setSelectedUser(null);
                            setBalanceAmount('');
                            setBalanceReason('');
                          }
                        }}>
                          <DialogTrigger asChild>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedUser(user.user_id);
                                setBalanceDialogOpen(true);
                              }}
                            >
                              <Icon name="Wallet" size={14} className="mr-1" />
                              Изменить
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Изменить баланс пользователя</DialogTitle>
                              <DialogDescription>
                                {user.first_name} (@{user.username || user.user_id})<br />
                                Текущий баланс: {user.balance} кредитов
                              </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                              <div className="space-y-2">
                                <Label htmlFor="amount">Сумма изменения (может быть отрицательной)</Label>
                                <Input
                                  id="amount"
                                  type="number"
                                  placeholder="Например: 100 или -50"
                                  value={balanceAmount}
                                  onChange={(e) => setBalanceAmount(e.target.value)}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="reason">Причина изменения</Label>
                                <Input
                                  id="reason"
                                  placeholder="Например: Компенсация за ошибку"
                                  value={balanceReason}
                                  onChange={(e) => setBalanceReason(e.target.value)}
                                />
                              </div>
                              {balanceAmount && (
                                <p className="text-sm text-muted-foreground">
                                  Новый баланс: {user.balance + parseInt(balanceAmount || '0')} кредитов
                                </p>
                              )}
                            </div>
                            <DialogFooter>
                              <Button variant="outline" onClick={() => setBalanceDialogOpen(false)}>
                                Отмена
                              </Button>
                              <Button onClick={handleUpdateBalance} disabled={updating || !balanceAmount}>
                                {updating ? 'Обновление...' : 'Применить'}
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
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
            <Card className="mb-4">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Icon name="Sparkles" size={24} />
                  Статистика по AI моделям
                </CardTitle>
                <CardDescription>Использование генераторов изображений и видео</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {data.model_stats && data.model_stats.length > 0 ? (
                    data.model_stats.map((model) => (
                      <Card key={model.order_type} className="bg-gradient-to-br from-purple-50 to-pink-50">
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <Icon name={getOrderTypeIcon(model.order_type)} className="text-primary" size={28} />
                            <Badge variant="outline">{model.total_count}</Badge>
                          </div>
                          <CardTitle className="text-lg">{getOrderTypeLabel(model.order_type)}</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Успешно:</span>
                            <span className="font-medium text-green-600">{model.completed_count}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Ошибки:</span>
                            <span className="font-medium text-red-600">{model.failed_count}</span>
                          </div>
                          <div className="flex justify-between pt-2 border-t">
                            <span className="text-muted-foreground">Выручка:</span>
                            <span className="font-bold text-primary">{model.total_revenue}₽</span>
                          </div>
                        </CardContent>
                      </Card>
                    ))
                  ) : (
                    <p className="col-span-4 text-center text-muted-foreground py-8">Статистика пока недоступна</p>
                  )}
                </div>
              </CardContent>
            </Card>

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