import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:media_kit/media_kit.dart';

import 'core_bridge.dart';
import 'media_pipeline.dart';

Future<void> runPackageSmoke(List<String> arguments) async {
  if (arguments.length != 3) exit(2);
  final report = File(arguments[1]), input = arguments[2];
  final result = <String, Object?>{
    'ok': false,
    'nativeCore': false,
    'ffprobe': false,
    'remux': false,
    'mediaKitPlayback': false,
  };
  Player? player;
  try {
    final repository = NativeRepository();
    await repository.initialize();
    result['nativeCore'] = true;
    final executor = FFmpegExecutor();
    final probe = await executor.probe(input);
    verifyMediaDuration(probe, 3);
    result['ffprobe'] = true;
    final remuxed = File(
      '${report.parent.path}${Platform.pathSeparator}remuxed.mkv',
    );
    await executor.run([
      '-i',
      input,
      '-map',
      '0:v:0',
      '-c',
      'copy',
      remuxed.path,
    ]);
    verifyMediaDuration(await executor.probe(remuxed.path), 3);
    result['remux'] = true;
    try {
      player = Player(
        configuration: const PlayerConfiguration(muted: true, vo: 'null'),
      );
      await player.setAudioTrack(AudioTrack.no());
      final advancing = player.stream.position.firstWhere(
        (time) => time.inMilliseconds >= 400,
      );
      await player.open(Media(remuxed.path));
      await advancing.timeout(const Duration(seconds: 12));
      result['mediaKitPlayback'] = true;
    } on TimeoutException {
      result['playbackNote'] = '播放推进自检超时：构建机通常没有音频/图形设备，需在实机复验';
    }
    result['ok'] = true;
    await report.writeAsString(jsonEncode(result), flush: true);
    await player?.dispose();
    exit(result['mediaKitPlayback'] == true ? 0 : 3);
  } catch (error) {
    result['error'] = error.toString();
    await player?.dispose();
    await report.writeAsString(jsonEncode(result), flush: true);
    exit(1);
  }
}
