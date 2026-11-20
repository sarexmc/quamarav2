package dev.qumara.combat.attack;

import dev.qumara.combat.DangerShape;
import dev.qumara.combat.DangerZone;
import dev.qumara.combat.RootedManager;
import dev.qumara.entity.QumaraEntity;
import dev.qumara.registry.ModSounds;
import dev.qumara.vfx.Vfx;
import net.minecraft.block.Blocks;
import net.minecraft.entity.LivingEntity;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.util.math.Vec3d;

import java.util.ArrayList;
import java.util.List;

/** ATAQUE 1 - RAICES ATRAPADORAS. Circulos rojos donde emergen las raices; atrapan e inmovilizan. */
public class RootsAttack extends BossAttack {
    public static final float IMPACT = 26f, TOTAL = 48f, RADIUS = 1.7f;
    private final List<DangerZone> roots = new ArrayList<>();

    @Override public String animation() { return "roots_cast"; }
    @Override public float total() { return TOTAL; }

    @Override
    public void start(QumaraEntity b, LivingEntity target) {
        List<ServerPlayerEntity> ps = b.players();
        List<Vec3d> pts = new ArrayList<>();
        int total = b.fury() ? 9 : 5;
        // 1) una raiz sobre la posicion prevista de cada objetivo (max 3)
        for (int i = 0; i < Math.min(3, ps.size()); i++) {
            ServerPlayerEntity p = ps.get(i);
            Vec3d lead = p.getPos().add(p.getVelocity().multiply(b.ticks(IMPACT) * 0.5, 0, b.ticks(IMPACT) * 0.5));
            tryAdd(pts, new Vec3d(lead.x, p.getY(), lead.z), b, 1.5);
        }
        // 2) resto repartidas alrededor de los jugadores / arena
        int guard = 0;
        while (pts.size() < total && guard++ < 80) {
            Vec3d c = ps.isEmpty() ? b.getPos() : ps.get(b.rng().nextInt(ps.size())).getPos();
            double a = b.rng().nextDouble() * Math.PI * 2, r = 2.5 + b.rng().nextDouble() * 6.5;
            tryAdd(pts, new Vec3d(c.x + Math.cos(a) * r, c.y, c.z + Math.sin(a) * r), b, 2.4);
        }
        for (Vec3d p : pts) {
            double y = b.groundY(p.x, p.z);
            roots.add(show(b, new DangerShape.Circle(p.x, p.z, RADIUS), y, IMPACT, 8f, DangerZone.ROOTS));
        }
        b.sound(ModSounds.WARNING, 2.0f, 0.8f);
        b.sound(ModSounds.EARTH_CRACK, 2.5f, 1.2f);
    }

    private void tryAdd(List<Vec3d> pts, Vec3d p, QumaraEntity b, double minSep) {
        if (p.squaredDistanceTo(b.getPos().x, p.y, b.getPos().z) < 3.5 * 3.5 || p.squaredDistanceTo(b.getPos().x, p.y, b.getPos().z) > 22 * 22) return;
        for (Vec3d q : pts) if (q.squaredDistanceTo(p.x, q.y, p.z) < minSep * minSep) return;
        pts.add(p);
    }

    @Override
    public void tick(QumaraEntity b, float prev, float now) {
        if (crossed(prev, now, 10f)) b.sound(ModSounds.ROOTS_GROW, 2.5f, 0.7f);
        // pequeñas sacudidas de tierra durante el aviso
        if (now < IMPACT && (int) now % 3 == 0)
            for (DangerZone z : roots) if (z.shape() instanceof DangerShape.Circle c)
                Vfx.burst(b.sw(), Vfx.DIRT, new Vec3d(c.x(), z.y() + 0.1, c.z()), 2, 0.7, 0.03);
        if (crossed(prev, now, IMPACT)) {
            for (DangerZone z : roots) {
                DangerShape.Circle c = (DangerShape.Circle) z.shape();
                Vec3d at = new Vec3d(c.x(), z.y(), c.z());
                Vfx.rootEruption(b.sw(), at);
                float[] h = {3.2f, 2.5f, 2.0f}, tx = {0, 16, -10}, tz = {0, -8, 18}, yaw = {0, 120, 240};
                for (int i = 0; i < 3; i++)
                    b.plants().sprout(Blocks.MANGROVE_ROOTS.getDefaultState(), at.add(Math.cos(Math.toRadians(yaw[i])) * 0.3 * i, 0, Math.sin(Math.toRadians(yaw[i])) * 0.3 * i),
                            1.1f - 0.15f * i, h[i], tx[i], tz[i], yaw[i], 0, 5, 36, 10);
                for (ServerPlayerEntity p : b.zones().playersIn(z)) {
                    b.hurtPlayer(p, 5f);
                    RootedManager.root(p, 50);
                    p.setVelocity(0, 0.25, 0); p.velocityModified = true;
                }
            }
            b.sound(ModSounds.ROOTS_GROW, 3.5f, 0.9f);
            b.sound(ModSounds.EARTH_CRACK, 3.0f, 1.0f);
            b.shake(10, 0.3f);
        }
    }
}
