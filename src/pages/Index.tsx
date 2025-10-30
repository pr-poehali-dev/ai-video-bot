import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';
import StatsCards from '@/components/dashboard/StatsCards';
import RecentUsers from '@/components/dashboard/RecentUsers';
import RecentOrders from '@/components/dashboard/RecentOrders';
import OrderStats from '@/components/dashboard/OrderStats';
import DailyRevenue from '@/components/dashboard/DailyRevenue';
import ModelStats from '@/components/dashboard/ModelStats';

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

  const handleOpenBalanceDialog = (userId: number) => {
    setSelectedUser(userId);
    setBalanceDialogOpen(true);
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
          <div className="flex gap-2">
            <Button onClick={loadDashboard} variant="outline" size="sm">
              <Icon name="RefreshCw" size={16} className="mr-2" />
              Обновить
            </Button>
            <Button 
              onClick={handleResetStats} 
              variant="destructive" 
              size="sm"
              disabled={resettingStats}
            >
              <Icon name="Trash2" size={16} className="mr-2" />
              {resettingStats ? 'Сброс...' : 'Сбросить статистику'}
            </Button>
          </div>
        </div>

        <StatsCards stats={data.stats} />

        <Tabs defaultValue="users" className="space-y-4">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="users">Пользователи</TabsTrigger>
            <TabsTrigger value="orders">Заказы</TabsTrigger>
            <TabsTrigger value="stats">Статистика</TabsTrigger>
            <TabsTrigger value="revenue">Доходы</TabsTrigger>
            <TabsTrigger value="models">Модели</TabsTrigger>
          </TabsList>

          <TabsContent value="users">
            <RecentUsers 
              users={data.recent_users} 
              onUpdateBalance={handleOpenBalanceDialog}
            />
          </TabsContent>

          <TabsContent value="orders">
            <RecentOrders orders={data.recent_orders} />
          </TabsContent>

          <TabsContent value="stats">
            <OrderStats stats={data.order_stats} />
          </TabsContent>

          <TabsContent value="revenue">
            <DailyRevenue stats={data.daily_revenue} />
          </TabsContent>

          <TabsContent value="models">
            <ModelStats stats={data.model_stats} />
          </TabsContent>
        </Tabs>

        <Dialog open={balanceDialogOpen} onOpenChange={setBalanceDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Изменить баланс пользователя</DialogTitle>
              <DialogDescription>
                Введите сумму для изменения баланса (положительную или отрицательную)
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="amount">Сумма (₽)</Label>
                <Input
                  id="amount"
                  type="number"
                  placeholder="Например: 100 или -50"
                  value={balanceAmount}
                  onChange={(e) => setBalanceAmount(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="reason">Причина (необязательно)</Label>
                <Input
                  id="reason"
                  placeholder="Например: Бонус за активность"
                  value={balanceReason}
                  onChange={(e) => setBalanceReason(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button 
                variant="outline" 
                onClick={() => setBalanceDialogOpen(false)}
                disabled={updating}
              >
                Отмена
              </Button>
              <Button onClick={handleUpdateBalance} disabled={updating}>
                {updating ? 'Обновление...' : 'Применить'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
