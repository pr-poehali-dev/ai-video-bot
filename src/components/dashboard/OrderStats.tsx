import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';

interface OrderStat {
  order_type: string;
  count: number;
  total_cost: number;
}

interface OrderStatsProps {
  stats: OrderStat[];
}

export default function OrderStats({ stats }: OrderStatsProps) {
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

  const maxCount = Math.max(...stats.map(s => s.count), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="BarChart3" size={20} />
          Статистика по типам заказов
        </CardTitle>
        <CardDescription>Распределение заказов по типам</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {stats.map((stat) => (
          <div key={stat.order_type} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name={getOrderTypeIcon(stat.order_type)} size={18} className="text-muted-foreground" />
                <span className="font-medium">{getOrderTypeLabel(stat.order_type)}</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {stat.count} заказов • {stat.total_cost}₽
              </div>
            </div>
            <Progress value={(stat.count / maxCount) * 100} className="h-2" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
