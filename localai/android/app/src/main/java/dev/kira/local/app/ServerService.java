package dev.kira.local.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/** Держит процесс живым, пока идут загрузки моделей и генерация. */
public class ServerService extends Service {
    private static final String CHANNEL = "kira_server";

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "STOP".equals(intent.getAction())) {
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Kira Local", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new Notification.Builder(this, CHANNEL)
                .setContentTitle("Kira Local работает")
                .setContentText("Локальный ИИ активен — загрузки и модели продолжаются")
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentIntent(open)
                .addAction(new Notification.Action.Builder(null, "Остановить",
                        PendingIntent.getService(this, 1, new Intent(this, ServerService.class).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE)).build())
                .setOngoing(true)
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            else startForeground(1, n);
            ServerHolder.ensure(this);
        } catch (Exception e) {
            stopSelf();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        ServerHolder.stop();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
