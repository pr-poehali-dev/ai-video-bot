import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';

interface ModelStat {
  order_type: string;
  total_count: number;
  completed_count: number;
  failed_count: number;
  total_revenue: number;
}

interface ModelStatsProps {
  stats: ModelStat[];
}

export default function ModelStats({ stats }: ModelStatsProps) {
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="Activity" size={20} />
          Статистика моделей
        </CardTitle>
        <CardDescription>Эффективность каждой модели генерации</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {stats.map((stat) => {
          const successRate = stat.total_count > 0 
            ? (stat.completed_count / stat.total_count) * 100 
            : 0;
          
          return (
            <div key={stat.order_type} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon name={getOrderTypeIcon(stat.order_type)} size={20} className="text-primary" />
                  <span className="font-semibold">{getOrderTypeLabel(stat.order_type)}</span>
                </div>
                <Badge variant="outline" className="text-green-600">
                  {stat.total_revenue}₽
                </Badge>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{stat.total_count}</div>
                  <div className="text-xs text-muted-foreground">Всего</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{stat.completed_count}</div>
                  <div className="text-xs text-muted-foreground">Успешно</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-600">{stat.failed_count}</div>
                  <div className="text-xs text-muted-foreground">Ошибки</div>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Успешность</span>
                  <span className="font-medium">{successRate.toFixed(1)}%</span>
                </div>
                <Progress value={successRate} className="h-2" />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
