import 'dart:io';
import 'package:hive/hive.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' show join;
import 'package:progresstracker/progress_data.dart';

class PhotoManager {
  static final PhotoManager manager = PhotoManager();
  final String photoProgressBox = 'photoProgress';
  var cachedProgressList;
  bool isHiveInitialized = false;

  ///Static methods
  static Future<String> getLocalPath() async {
    final directory = await getApplicationDocumentsDirectory();
    return directory.path;
  }

  static int todayStartTimeInSeconds() {
    DateTime now = new DateTime.now(); //local
    DateTime dayStartTime = new DateTime(now.year, now.month, now.day);
    var ms = dayStartTime.millisecondsSinceEpoch;
    return (ms / 1000).round();
  }

  static int nowTimeInSeconds() {
    DateTime now = new DateTime.now(); //local
    var ms = now.millisecondsSinceEpoch;
    return (ms / 1000).round();
  }

  ///Internal methods for public manager instance.
  Future saveProgressPictures(String frontPictureSource,
      String sidePictureSource, String backPictureSource) async {
    final time = nowTimeInSeconds();
    final todayStartTime = todayStartTimeInSeconds();

    try {
      final String path = (await getApplicationDocumentsDirectory()).path;
      print(join(path, '${time}_front'));

      //copy images to local documents directory
      var tempFile = File(frontPictureSource);
      final File newImage =
          await tempFile.copy(join(path, '${time}_front.jpg'));
      tempFile = File(sidePictureSource);
      final File newImage2 =
          await tempFile.copy(join(path, '${time}_side.jpg'));
      tempFile = File(backPictureSource);
      final File newImage3 =
          await tempFile.copy(join(path, '${time}_back.jpg'));

      //save the paths to the pictures in local Hive db
      await initHive();
      var box = await Hive.openBox('photoProgress');

      var progress = PhotoProgress()
        ..frontPictureSource = '${time}_front.jpg'
        ..sidePictureSource = '${time}_side.jpg'
        ..backPictureSource = '${time}_back.jpg'
        ..date = todayStartTime;

      box.add(progress);
      box.close();
    } catch (error) {
      print(error);
      return;
    }
  }

  Future<List> getPhotoProgressList() async {
    await initHive();
    var box = await Hive.openBox(photoProgressBox);
    List list = box.values.toList();
    cachedProgressList = list;

    box.close();
    return list;
  }

  Future<PhotoProgress> getLastPhotoProgress() async {
    await initHive();
    var box = await Hive.openBox(photoProgressBox);
    PhotoProgress last = box.values.last;
    box.close();
    return last;
  }

  Future initHive() async {
    if (!isHiveInitialized) {
      await Hive.initFlutter();
      Hive.registerAdapter(PhotoProgressAdapter());
      isHiveInitialized = true;
    }
  }
}
