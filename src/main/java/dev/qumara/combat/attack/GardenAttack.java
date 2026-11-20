package dev.qumara.combat.attack;

import dev.qumara.combat.DangerShape;
import dev.qumara.combat.DangerZone;
import dev.qumara.combat.Lingering;
import dev.qumara.combat.RootedManager;
import dev.qumara.entity.QumaraEntity;
import dev.qumara.registry.ModSounds;
import dev.qumara.vfx.Vfx;
import dev.qumara.world.ArenaTransformer;
import net.minecraft.block.Blocks;
import net.minecraft.block.SweetBerryBushBlock;
import net.minecraft.entity.LivingEntity;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Vec3d;

import java.util.ArrayList;
import java.util.List;

/**
 * ATAQUE 5 - JARDIN MALDITO. Plantas que atrapan (GRAB), plantas de espinas que dañan por tiempo (THORN) y obstaculos
 * solidos (OBSTACLE, bloques reales temporales). La arena se transforma en musgo y se restaura despues.
 */
public class GardenAttack extends BossAttack {
    public static final float IMPACT = 36f, TOTAL = 60f;
    private record Plant(DangerZone zone, int kind, Vec3d at, float radius) {}
    private final List<Plant> plants = new ArrayList<>();

    @Override public String animation() { return "garden_cast"; }
    @Override public float total() { return TOTAL; }

    @Override
    public void start(QumaraEntity b, LivingEntity target) {
        int n = b.fury() ? 16 : 10;
        List<ServerPlayerEntity> ps = b.players();
        List<Vec3d> pts = new ArrayList<>();
        int guard = 0;
        while (pts.size() < n && guard++ < 300) {
            Vec3d p;
            if (pts.size() < 2 && !ps.isEmpty()) {                 // dos plantas sobre jugadores
                ServerPlayerEntity t = ps.get(pts.size() % ps.size());
                p = t.getPos().add((b.rng().nextDouble() - .5) * 3, 0, (b.rng().nextDouble() - .5) * 3);
            } else {
                double a = b.rng().nextDouble() * Math.PI * 2, r = 4.5 + b.rng().nextDouble() * 11.5;
                p = b.getPos().add(Math.cos(a) * r, 0, Math.sin(a) * r);
            }
            if (p.squaredDistanceTo(b.getPos().x, p.y, b.getPos().z) < 4.2 * 4.2) continue;
            boolean ok = true;
            for (Vec3d q : pts) if (q.squaredDistanceTo(p.x, q.y, p.z) < 3.1 * 3.1) { ok = false; break; }
            if (ok) pts.add(p);
        }
        for (int i = 0; i < pts.size(); i++) {
            Vec3d p = pts.get(i);
            int kind = i % 10 < 4 ? 0 : (i % 10 < 7 ? 1 : 2);     // 0 = grab, 1 = thorn, 2 = obstaculo
            float r = kind == 0 ? 1.8f : (kind == 1 ? 1.6f : 1.2f);
            double y = b.groundY(p.x, p.z);
            int style = kind == 0 ? DangerZone.GARDEN : (kind == 1 ? DangerZone.THORN : DangerZone.OBSTACLE);
            float linger = kind == 1 ? 62f : 6f;                   // las espinas siguen dañando: la zona permanece visible
            plants.add(new Plant(show(b, new DangerShape.Circle(p.x, p.z, r), y, IMPACT, linger, style), kind, new Vec3d(p.x, y, p.z), r));
        }
        BlockPos c = b.getBlockPos();
        long now = b.sw().getTime();
        b.arena().mossDisc(b.sw(), c, 17, now + b.ticks(20f), b.ticks(IMPACT) + 150);
        b.sound(ModSounds.WARNING, 2.5f, 0.7f);
        b.sound(ModSounds.GARDEN_BLOOM, 3.0f, 0.6f);
    }

    @Override
    public void tick(QumaraEntity b, float prev, float now) {
        if (now < IMPACT && (int) now % 4 == 0)
            for (Plant pl : plants) Vfx.burst(b.sw(), Vfx.MOSS, pl.at.add(0, 0.2, 0), 2, 0.8, 0.03);
        if (!crossed(prev, now, IMPACT)) return;
        long t = b.sw().getTime();
        for (Plant pl : plants) {
            switch (pl.kind) {
                case 0 -> {
                    Vfx.gardenBloom(b.sw(), pl.at);
                    b.plants().sprout(Blocks.MANGROVE_ROOTS.getDefaultState(), pl.at, 0.9f, 2.2f, 0, 0, 0, 0, 6, 40, 10);
                    b.plants().sprout(Blocks.FLOWERING_AZALEA_LEAVES.getDefaultState(), pl.at.add(0, 1.6, 0), 2.1f, 1.5f, 0, 0, 0, 2, 6, 38, 10);
                    for (ServerPlayerEntity p : b.zones().playersIn(pl.zone)) { b.hurtPlayer(p, 3f); RootedManager.root(p, 40); }
                }
                case 1 -> {
                    Vfx.gardenBloom(b.sw(), pl.at);
                    b.plants().sprout(Blocks.SWEET_BERRY_BUSH.getDefaultState().with(SweetBerryBushBlock.AGE, 3), pl.at, 1.9f, 1.7f, 0, 0, 0, 0, 6, 64, 10);
                    b.addLingering(new Thorns(pl.zone, t));
                }
                default -> {
                    BlockPos g = ArenaTransformer.groundAbove(b.sw(), (int) Math.floor(pl.at.x), (int) Math.floor(pl.at.z), (int) pl.at.y);
                    for (int h = 0; h < 3; h++) b.arena().place(g.up(h), Blocks.MANGROVE_ROOTS.getDefaultState(), t + h * 3L);
                    Vfx.rootEruption(b.sw(), pl.at);
                }
            }
        }
        b.arena().scheduleRestore(t + 150);
        b.sound(ModSounds.GARDEN_BLOOM, 4.0f, 0.8f);
        b.sound(ModSounds.ROOTS_GROW, 3.0f, 0.7f);
        b.shake(12, 0.35f);
    }

    /** Daño periodico en una zona de espinas mientras exista. */
    private static final class Thorns implements Lingering {
        private final DangerZone zone; private final long born;
        Thorns(DangerZone zone, long born) { this.zone = zone; this.born = born; }
        @Override
        public boolean tick(QumaraEntity b) {
            long age = b.sw().getTime() - born;
            if (age % 10 == 0)
                for (ServerPlayerEntity p : b.zones().playersIn(zone)) b.hurtPlayer(p, 2f);
            return age >= 62;
        }
    }
}
